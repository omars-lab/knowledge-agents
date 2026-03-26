/* ── Chat UI ──────────────────────────────────────────────────────────── */
(function () {
  "use strict";

  // ── Configuration ────────────────────────────────────────────────────
  // In production, Kong routes /api -> claude-agent:8000 (same origin).
  // In local dev (port 8080), nginx serves UI only — talk to claude-agent directly.
  const API_BASE = window.location.port === "8080"
    ? "http://localhost:8004/api/v1"
    : "/api/v1";
  const STORAGE_KEY = "chat_sessions";
  const DEMO_MODE = new URLSearchParams(window.location.search).has("demo");

  // ── DOM refs ─────────────────────────────────────────────────────────
  const sidebar = document.getElementById("sidebar");
  const sidebarOverlay = document.getElementById("sidebar-overlay");
  const sessionList = document.getElementById("session-list");
  const messagesEl = document.getElementById("messages");
  const chatForm = document.getElementById("chat-form");
  const messageInput = document.getElementById("message-input");
  const sendBtn = document.getElementById("send-btn");
  const menuBtn = document.getElementById("menu-btn");
  const newChatBtn = document.getElementById("new-chat-btn");
  const errorBanner = document.getElementById("error-banner");
  const errorText = document.getElementById("error-text");
  const errorDismiss = document.getElementById("error-dismiss");

  // ── State ────────────────────────────────────────────────────────────
  let sessions = loadSessions();
  let activeSessionId = null;
  let streaming = false;
  let abortController = null;

  // ── Markdown setup ───────────────────────────────────────────────────
  marked.setOptions({
    highlight: function (code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return hljs.highlightAuto(code).value;
    },
    breaks: true,
  });

  // ── Init ─────────────────────────────────────────────────────────────
  renderSessionList();
  if (sessions.length > 0) {
    switchSession(sessions[0].id);
  }

  // Auto-launch demo mode
  if (DEMO_MODE) {
    console.log("[chat] Demo mode activated");
    launchDemo();
  }

  // ── Events ───────────────────────────────────────────────────────────
  chatForm.addEventListener("submit", handleSubmit);

  messageInput.addEventListener("input", function () {
    sendBtn.disabled = !this.value.trim() || streaming;
    autoResize(this);
  });

  messageInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn.disabled) chatForm.requestSubmit();
    }
  });

  menuBtn.addEventListener("click", function () {
    sidebar.classList.toggle("open");
  });

  sidebarOverlay.addEventListener("click", function () {
    sidebar.classList.remove("open");
  });

  newChatBtn.addEventListener("click", startNewChat);
  errorDismiss.addEventListener("click", hideError);

  // ── Demo mode ──────────────────────────────────────────────────────
  async function launchDemo() {
    const demoText = "Show me everything — notes about goals, the knowledge graph, and my changelog";
    const session = createSession(demoText);
    activeSessionId = session.id;
    renderSessionList();

    session.messages.push({ role: "user", content: demoText });
    renderMessages(session);

    streaming = true;
    sendBtn.disabled = true;

    const thinkingEl = appendThinking();
    scrollToBottom();

    const assistantMsg = { role: "assistant", content: "", tools: [], meta: null };
    session.messages.push(assistantMsg);

    let firstToken = true;
    let currentToolPills = null;
    let contentEl = null;

    const ctx = {
      get firstToken() { return firstToken; },
      set firstToken(v) { firstToken = v; },
      get currentToolPills() { return currentToolPills; },
      set currentToolPills(v) { currentToolPills = v; },
      get contentEl() { return contentEl; },
      set contentEl(v) { contentEl = v; },
      thinkingEl,
      assistantMsg,
      session,
    };

    const { runDemo } = await import("./demo.js");
    await runDemo(function (event) {
      handleStreamEvent(event, ctx);
    });

    // Render metadata
    if (assistantMsg.meta && ctx.contentEl) {
      renderMetaLine(assistantMsg.meta, ctx.contentEl.parentElement);
    }

    saveSessions();
    streaming = false;
    sendBtn.disabled = false;
  }

  // ── Submit handler ───────────────────────────────────────────────────
  async function handleSubmit(e) {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text || streaming) return;

    if (!activeSessionId) {
      const session = createSession(text);
      activeSessionId = session.id;
      renderSessionList();
    }

    const session = getSession(activeSessionId);

    session.messages.push({ role: "user", content: text });
    renderMessages(session);
    saveSessions();

    messageInput.value = "";
    sendBtn.disabled = true;
    autoResize(messageInput);

    await streamResponse(session, text);
  }

  // ── SSE streaming ────────────────────────────────────────────────────
  async function streamResponse(session, text) {
    streaming = true;
    sendBtn.disabled = true;
    hideError();

    const thinkingEl = appendThinking();
    scrollToBottom();

    abortController = new AbortController();

    const assistantMsg = { role: "assistant", content: "", tools: [], meta: null };
    session.messages.push(assistantMsg);

    let firstToken = true;
    let currentToolPills = null;
    let contentEl = null;

    const ctx = {
      get firstToken() { return firstToken; },
      set firstToken(v) { firstToken = v; },
      get currentToolPills() { return currentToolPills; },
      set currentToolPills(v) { currentToolPills = v; },
      get contentEl() { return contentEl; },
      set contentEl(v) { contentEl = v; },
      thinkingEl,
      assistantMsg,
      session,
    };

    const streamUrl = `${API_BASE}/chat/stream`;
    console.log("[chat] POST %s session=%s", streamUrl, session.serverSessionId || "(new)");

    try {
      const response = await fetch(streamUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: session.serverSessionId || null,
        }),
        signal: abortController.signal,
      });

      if (!response.ok) {
        const status = response.status;
        console.error("[chat] HTTP %d from %s", status, streamUrl);
        if (status === 429) {
          showError("Rate limited. Please wait a moment before trying again.");
        } else {
          showError(`Server error (${status}). Please try again.`);
        }
        session.messages.pop();
        session.messages.pop();
        messageInput.value = text;
        thinkingEl.remove();
        saveSessions();
        streaming = false;
        sendBtn.disabled = false;
        return;
      }

      console.log("[chat] SSE stream connected");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6);

          if (payload === "[DONE]") {
            console.log("[chat] SSE stream done");
            continue;
          }

          let event;
          try {
            event = JSON.parse(payload);
          } catch {
            console.warn("[chat] Failed to parse SSE payload:", payload.slice(0, 100));
            continue;
          }

          if (event.type !== "text" && event.type !== "tool_input") {
            console.log("[chat] event: %s %s", event.type, event.name || "");
          }

          handleStreamEvent(event, ctx);
        }
      }

      if (assistantMsg.meta && ctx.contentEl) {
        renderMetaLine(assistantMsg.meta, ctx.contentEl.parentElement);
      }

    } catch (err) {
      if (err.name === "AbortError") {
        console.log("[chat] Request aborted by user");
        if (!assistantMsg.content) session.messages.pop();
      } else {
        console.error("[chat] Connection error:", err.message);
        showError("Connection lost. Please try again.");
        if (!assistantMsg.content) {
          session.messages.pop();
          session.messages.pop();
        }
        messageInput.value = text;
      }
      thinkingEl.remove();
    }

    if (ctx.firstToken) thinkingEl.remove();

    saveSessions();
    streaming = false;
    sendBtn.disabled = !messageInput.value.trim();
    abortController = null;
  }

  // ── Shared event handler (used by both SSE stream and demo mode) ────
  function handleStreamEvent(event, ctx) {
    // Remove thinking on first real event
    if (ctx.firstToken) {
      ctx.thinkingEl.remove();
      const msgEl = appendMessageEl("assistant");
      ctx.currentToolPills = msgEl.querySelector(".tool-pills");
      ctx.contentEl = msgEl.querySelector(".message-body");
      ctx.firstToken = false;
    }

    switch (event.type) {
      case "text":
        ctx.assistantMsg.content += event.content;
        ctx.contentEl.innerHTML = marked.parse(ctx.assistantMsg.content);
        renderMermaidBlocks(ctx.contentEl);
        scrollToBottom();
        break;

      case "tool_start":
        ctx.assistantMsg.tools.push({ name: event.name, status: "running" });
        renderToolPills(ctx.currentToolPills, ctx.assistantMsg.tools);
        scrollToBottom();
        break;

      case "tool_complete":
        for (const t of ctx.assistantMsg.tools) {
          if (t.name === event.name && t.status === "running") {
            t.status = "done";
            break;
          }
        }
        renderToolPills(ctx.currentToolPills, ctx.assistantMsg.tools);
        // Render structured card if present
        if (event.structured) {
          renderCard(event.structured, ctx.contentEl.parentElement);
        }
        // Render tool detail block if we have duration
        if (event.duration_ms != null) {
          renderToolDetail(event, ctx.contentEl.parentElement);
        }
        scrollToBottom();
        break;

      case "tool_input":
        break;

      case "result":
        ctx.session.serverSessionId = event.session_id;
        ctx.assistantMsg.meta = {
          cost: event.cost_usd,
          turns: event.turns,
          session_id: event.session_id,
        };
        if (ctx.session.messages.filter(m => m.role === "assistant").length === 1) {
          ctx.session.title = ctx.assistantMsg.content.slice(0, 60).replace(/\n/g, " ") || ctx.session.title;
          renderSessionList();
        }
        break;

      case "error":
        showError(event.message || "An error occurred during streaming.");
        break;
    }
  }

  // ── Card renderers ─────────────────────────────────────────────────
  function renderCard(structured, container) {
    switch (structured.card_type) {
      case "note_cards":
        for (const card of structured.data) {
          container.appendChild(renderNoteCard(card));
        }
        break;
      case "graph":
        container.appendChild(renderGraphCard(structured.data));
        break;
      case "links":
        container.appendChild(renderLinkPills(structured.data));
        break;
      case "changelog":
        container.appendChild(renderChangelog(structured.data));
        break;
      default:
        console.warn("[chat] Unknown card_type:", structured.card_type);
    }
  }

  // ── Note Card ──────────────────────────────────────────────────────
  const NOTE_TYPE_CONFIG = {
    daily:    { icon: "\u{1F4C5}", accent: "#38bdf8", label: "Daily Note" },
    weekly:   { icon: "\u{1F4C6}", accent: "#818cf8", label: "Weekly Note" },
    plan:     { icon: "\u{1F3AF}", accent: "#f59e0b", label: "Plan" },
    template: { icon: "\u{1F4CB}", accent: "#a78bfa", label: "Template" },
    project:  { icon: "\u{1F4C1}", accent: "#50C878", label: "Project" },
    quip:     { icon: "\u{1F4DD}", accent: "#F2A93B", label: "Quip Doc" },
    file:     { icon: "\u{1F4BB}", accent: "#64748b", label: "File" },
    note:     { icon: "\u{1F5D2}", accent: "#64748b", label: "Note" },
  };

  function renderNoteCard(card) {
    const cfg = NOTE_TYPE_CONFIG[card.note_type] || NOTE_TYPE_CONFIG.note;
    const el = document.createElement("div");
    el.className = "card note-card";
    el.style.borderLeftColor = cfg.accent;

    // Action button
    let actionBtn = "";
    if (card.note_type === "quip" && card.quip_url) {
      actionBtn = `<a href="${escapeAttr(card.quip_url)}" target="_blank" rel="noopener" class="card-action card-action--quip">Open in Quip</a>`;
    } else if (card.note_type === "file" && card.vscode_url) {
      actionBtn = `<a href="${escapeAttr(card.vscode_url)}" class="card-action card-action--vscode">Open in VS Code</a>`;
    } else if (card.xcallback_url) {
      actionBtn = `<a href="${escapeAttr(card.xcallback_url)}" class="card-action card-action--noteplan">Open in NotePlan</a>`;
    }

    // Similarity badge
    const simBadge = card.similarity_score != null
      ? `<span class="card-badge" style="background:${similarityColor(card.similarity_score)}">${Math.round(card.similarity_score * 100)}%</span>`
      : "";

    // Status/type badge
    const typeBadge = card.note_type === "template"
      ? '<span class="card-badge card-badge--dim">Template</span>'
      : card.language
        ? `<span class="card-badge card-badge--dim">${escapeHtml(card.language)}</span>`
        : "";

    // Task stats
    const taskBar = card.task_stats
      ? `<div class="card-tasks"><div class="card-tasks-bar"><div class="card-tasks-fill" style="width:${Math.round((card.task_stats.done / card.task_stats.total) * 100)}%"></div></div><span class="card-tasks-label">${card.task_stats.done}/${card.task_stats.total} tasks</span></div>`
      : "";

    // Modified date
    const modDate = card.modified_at && card.note_type !== "template"
      ? `<span class="card-date">${formatDate(card.modified_at)}</span>`
      : "";

    // Folder breadcrumb
    const folder = card.folder && card.note_type === "note"
      ? `<span class="card-folder">${escapeHtml(card.folder)} &rsaquo; </span>`
      : card.folder && card.note_type === "file"
        ? `<span class="card-folder">${escapeHtml(card.folder)}/</span>`
        : "";

    el.innerHTML = `
      <div class="card-header">
        <span class="card-icon">${cfg.icon}</span>
        <span class="card-title">${folder}${escapeHtml(card.title)}</span>
        ${simBadge}${typeBadge}
      </div>
      <div class="card-preview">${escapeHtml(card.preview || "")}</div>
      ${taskBar}
      <div class="card-footer">
        ${actionBtn}
        ${modDate}
      </div>
    `;
    return el;
  }

  function similarityColor(score) {
    const r = Math.round(255 * (1 - score));
    const g = Math.round(200 * score);
    return `rgba(${r}, ${g}, 80, 0.2)`;
  }

  // ── Graph Card (stub — renders node/edge count, placeholder for mermaid/vis-network) ──
  function renderGraphCard(data) {
    const el = document.createElement("div");
    el.className = "card graph-card";

    const nodeCount = data.nodes ? data.nodes.length : 0;
    const edgeCount = data.edges ? data.edges.length : 0;

    // Render a simple node list for now (Phase B will add mermaid/vis-network)
    const nodeList = (data.nodes || []).map(n => {
      return `<span class="graph-node" style="background:${n.color || '#666'}22;border-color:${n.color || '#666'}">${escapeHtml(n.name)}<span class="graph-node-type">${escapeHtml(n.type)}</span></span>`;
    }).join("");

    const edgeList = (data.edges || []).slice(0, 10).map(e => {
      const src = (data.nodes || []).find(n => n.id === e.source);
      const tgt = (data.nodes || []).find(n => n.id === e.target);
      return `<span class="graph-edge">${escapeHtml(src?.name || e.source)} <span class="graph-edge-label">${escapeHtml(e.label)}</span> ${escapeHtml(tgt?.name || e.target)}</span>`;
    }).join("");

    el.innerHTML = `
      <div class="card-header">
        <span class="card-icon">\u{1F578}</span>
        <span class="card-title">Knowledge Graph</span>
        <span class="card-badge card-badge--dim">${nodeCount} nodes \u00b7 ${edgeCount} edges</span>
      </div>
      <div class="graph-nodes">${nodeList}</div>
      <div class="graph-edges">${edgeList}</div>
    `;
    return el;
  }

  // ── Link Pills ────────────────────────────────────────────────────
  const LINK_TYPE_CONFIG = {
    noteplan: { color: "#38bdf8", icon: "\u{1F4F1}", label: "app" },
    quip:     { color: "#F2A93B", icon: "\u{1F4DD}", label: "browser" },
    vscode:   { color: "#007ACC", icon: "\u{1F4BB}", label: "app" },
    github:   { color: "#8b949e", icon: "\u{1F419}", label: "browser" },
    email:    { color: "#34d399", icon: "\u{2709}", label: "app" },
    location: { color: "#f87171", icon: "\u{1F4CD}", label: "browser" },
    web:      { color: "#a78bfa", icon: "\u{1F310}", label: "browser" },
  };

  function renderLinkPills(links) {
    const el = document.createElement("div");
    el.className = "link-pills";
    el.innerHTML = links.map(link => {
      const cfg = LINK_TYPE_CONFIG[link.type] || LINK_TYPE_CONFIG.web;
      const target = cfg.label === "browser" ? ' target="_blank" rel="noopener"' : "";
      return `<a href="${escapeAttr(link.url)}" class="link-pill" style="--pill-color:${cfg.color}"${target}>${cfg.icon} ${escapeHtml(link.label)}<span class="link-pill-hint">${cfg.label}</span></a>`;
    }).join("");
    return el;
  }

  // ── Changelog Timeline ────────────────────────────────────────────
  const CHANGELOG_ACTIONS = {
    new:     { color: "#34d399", icon: "+" },
    updated: { color: "#38bdf8", icon: "\u2191" },
    deleted: { color: "#f87171", icon: "\u2212" },
  };

  function renderChangelog(data) {
    const el = document.createElement("div");
    el.className = "card changelog-card";

    let currentDate = "";
    const entriesHtml = (data.entries || []).map(entry => {
      const cfg = CHANGELOG_ACTIONS[entry.action] || CHANGELOG_ACTIONS.updated;
      let dateHeader = "";
      if (entry.date !== currentDate) {
        currentDate = entry.date;
        dateHeader = `<div class="changelog-date">${formatDate(entry.date)}</div>`;
      }
      return `${dateHeader}<div class="changelog-entry"><span class="changelog-dot" style="background:${cfg.color}">${cfg.icon}</span><span class="changelog-summary">${escapeHtml(entry.summary)}</span>${entry.detail ? `<span class="changelog-detail">${escapeHtml(entry.detail)}</span>` : ""}</div>`;
    }).join("");

    el.innerHTML = `
      <div class="card-header">
        <span class="card-icon">\u{1F4C8}</span>
        <span class="card-title">Changelog: ${escapeHtml(data.start_date)} \u2192 ${escapeHtml(data.end_date)}</span>
      </div>
      <div class="changelog-timeline">${entriesHtml}</div>
    `;
    return el;
  }

  // ── Tool Detail Block ─────────────────────────────────────────────
  function renderToolDetail(event, container) {
    const el = document.createElement("div");
    el.className = "tool-detail collapsed";

    const durationSec = (event.duration_ms / 1000).toFixed(1);

    el.innerHTML = `
      <div class="tool-detail-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <span class="tool-detail-chevron">\u25B6</span>
        <span class="tool-detail-name">${escapeHtml(event.name)}</span>
        <span class="tool-detail-duration">${durationSec}s</span>
      </div>
      <div class="tool-detail-body">
        <div class="tool-detail-row"><span class="tool-detail-label">Input</span><pre class="tool-detail-json">${escapeHtml(event.input || "")}</pre></div>
        ${event.output_text ? `<div class="tool-detail-row"><span class="tool-detail-label">Output</span><pre class="tool-detail-json">${escapeHtml(event.output_text.slice(0, 500))}</pre></div>` : ""}
      </div>
    `;
    container.appendChild(el);
  }

  // ── Mermaid rendering (lazy-loaded) ────────────────────────────────
  let mermaidLoading = false;
  let mermaidReady = false;

  async function loadMermaid() {
    if (mermaidReady || mermaidLoading) return;
    mermaidLoading = true;
    console.log("[chat] Loading mermaid.js...");
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js";
    script.crossOrigin = "anonymous";
    script.onload = () => {
      window.mermaid.initialize({
        startOnLoad: false,
        theme: "dark",
        themeVariables: {
          darkMode: true,
          background: "#111118",
          primaryColor: "#a78bfa",
          primaryTextColor: "#e2e8f0",
          primaryBorderColor: "#a78bfa",
          lineColor: "#64748b",
          secondaryColor: "#1e1e2e",
          tertiaryColor: "#1e1e2e",
        },
      });
      mermaidReady = true;
      mermaidLoading = false;
      console.log("[chat] mermaid.js ready");
      // Re-render any pending blocks
      document.querySelectorAll(".mermaid-pending").forEach(renderOneMermaid);
    };
    document.head.appendChild(script);
  }

  function renderMermaidBlocks(container) {
    const codeBlocks = container.querySelectorAll("code.language-mermaid");
    if (codeBlocks.length === 0) return;

    // Lazy-load mermaid on first detection
    if (!mermaidReady && !mermaidLoading) loadMermaid();

    for (const code of codeBlocks) {
      const pre = code.parentElement;
      if (!pre || pre.dataset.mermaid) continue;
      pre.dataset.mermaid = "true";

      const wrapper = document.createElement("div");
      wrapper.className = mermaidReady ? "mermaid-wrapper" : "mermaid-wrapper mermaid-pending";
      wrapper.dataset.source = code.textContent;
      pre.replaceWith(wrapper);

      if (mermaidReady) {
        renderOneMermaid(wrapper);
      } else {
        // Show placeholder while loading
        wrapper.innerHTML = '<div class="mermaid-loading">Loading diagram...</div>';
      }
    }
  }

  async function renderOneMermaid(wrapper) {
    wrapper.classList.remove("mermaid-pending");
    const source = wrapper.dataset.source;
    try {
      const id = "mermaid-" + Math.random().toString(36).slice(2, 8);
      const { svg } = await window.mermaid.render(id, source);
      wrapper.innerHTML = svg;
      wrapper.classList.add("mermaid-rendered");
    } catch (err) {
      console.warn("[chat] Mermaid render failed:", err.message);
      // Fallback: show as code block
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      code.textContent = source;
      pre.appendChild(code);
      wrapper.replaceWith(pre);
    }
  }

  // ── Metadata line ─────────────────────────────────────────────────
  function renderMetaLine(meta, container) {
    const metaEl = document.createElement("div");
    metaEl.className = "message-meta";
    const parts = [];
    if (meta.cost != null) parts.push(`$${meta.cost.toFixed(4)}`);
    if (meta.turns != null) parts.push(`${meta.turns} turn${meta.turns !== 1 ? "s" : ""}`);
    metaEl.textContent = parts.join(" \u00b7 ");
    container.appendChild(metaEl);
  }

  // ── DOM helpers ──────────────────────────────────────────────────────
  function appendMessageEl(role) {
    const el = document.createElement("div");
    el.className = "message";
    el.innerHTML = `
      <span class="message-role">${role === "user" ? "You" : "Assistant"}</span>
      <div class="tool-pills"></div>
      <div class="message-body"></div>
    `;
    messagesEl.appendChild(el);
    return el;
  }

  function appendThinking() {
    const el = document.createElement("div");
    el.className = "thinking";
    el.innerHTML = `
      <div class="thinking-dots"><span></span><span></span><span></span></div>
      <span>Thinking...</span>
    `;
    messagesEl.appendChild(el);
    return el;
  }

  function renderToolPills(container, tools) {
    if (!container) return;
    container.innerHTML = tools
      .map(
        (t) =>
          `<span class="tool-pill">${
            t.status === "running" ? '<span class="spinner"></span>' : "\u2713"
          } ${t.name}</span>`
      )
      .join("");
  }

  function renderMessages(session) {
    messagesEl.innerHTML = "";
    for (const msg of session.messages) {
      const el = appendMessageEl(msg.role);
      const body = el.querySelector(".message-body");

      if (msg.role === "user") {
        body.textContent = msg.content;
      } else {
        body.innerHTML = marked.parse(msg.content || "");
        if (msg.tools && msg.tools.length > 0) {
          const pills = el.querySelector(".tool-pills");
          renderToolPills(pills, msg.tools);
        }
        if (msg.meta) {
          renderMetaLine(msg.meta, el);
        }
      }
    }
    scrollToBottom();
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // ── Error banner ─────────────────────────────────────────────────────
  function showError(msg) {
    errorText.textContent = msg;
    errorBanner.classList.remove("hidden");
  }

  function hideError() {
    errorBanner.classList.add("hidden");
  }

  // ── Auto-resize textarea ─────────────────────────────────────────────
  function autoResize(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }

  // ── Session management ───────────────────────────────────────────────
  function createSession(firstMessage) {
    const session = {
      id: crypto.randomUUID(),
      serverSessionId: null,
      title: firstMessage.slice(0, 60),
      messages: [],
      createdAt: Date.now(),
    };
    sessions.unshift(session);
    saveSessions();
    return session;
  }

  function getSession(id) {
    return sessions.find((s) => s.id === id);
  }

  function switchSession(id) {
    activeSessionId = id;
    const session = getSession(id);
    if (session) {
      renderMessages(session);
    }
    renderSessionList();
    sidebar.classList.remove("open");
  }

  function deleteSession(id) {
    sessions = sessions.filter((s) => s.id !== id);
    saveSessions();
    if (activeSessionId === id) {
      activeSessionId = sessions.length > 0 ? sessions[0].id : null;
      if (activeSessionId) {
        renderMessages(getSession(activeSessionId));
      } else {
        messagesEl.innerHTML = "";
      }
    }
    renderSessionList();
  }

  function startNewChat() {
    activeSessionId = null;
    messagesEl.innerHTML = "";
    messageInput.value = "";
    messageInput.focus();
    renderSessionList();
    sidebar.classList.remove("open");
  }

  function renderSessionList() {
    sessionList.innerHTML = sessions
      .map(
        (s) =>
          `<div class="session-item ${s.id === activeSessionId ? "active" : ""}" data-id="${s.id}">
            <span class="session-preview">${escapeHtml(s.title)}</span>
            <button class="session-delete" data-delete="${s.id}" title="Delete">&times;</button>
          </div>`
      )
      .join("");

    for (const el of sessionList.querySelectorAll(".session-item")) {
      el.addEventListener("click", function (e) {
        if (e.target.closest(".session-delete")) return;
        switchSession(this.dataset.id);
      });
    }
    for (const btn of sessionList.querySelectorAll(".session-delete")) {
      btn.addEventListener("click", function () {
        deleteSession(this.dataset.delete);
      });
    }
  }

  // ── Persistence ──────────────────────────────────────────────────────
  function saveSessions() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch {
      // localStorage full or unavailable
    }
  }

  function loadSessions() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }

  // ── Util ─────────────────────────────────────────────────────────────
  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function escapeAttr(str) {
    return str.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function formatDate(dateStr) {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch {
      return dateStr;
    }
  }
})();
