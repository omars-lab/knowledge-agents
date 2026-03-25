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
  let sessions = loadSessions();      // { id, title, messages: [{role, content, tools?, meta?}] }
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

  // ── Submit handler ───────────────────────────────────────────────────
  async function handleSubmit(e) {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text || streaming) return;

    // Create session if needed
    if (!activeSessionId) {
      const session = createSession(text);
      activeSessionId = session.id;
      renderSessionList();
    }

    const session = getSession(activeSessionId);

    // Add user message
    session.messages.push({ role: "user", content: text });
    renderMessages(session);
    saveSessions();

    // Reset input
    messageInput.value = "";
    sendBtn.disabled = true;
    autoResize(messageInput);

    // Stream response
    await streamResponse(session, text);
  }

  // ── SSE streaming ────────────────────────────────────────────────────
  async function streamResponse(session, text) {
    streaming = true;
    sendBtn.disabled = true;
    hideError();

    // Show thinking indicator
    const thinkingEl = appendThinking();
    scrollToBottom();

    abortController = new AbortController();

    // Prepare assistant message shell
    const assistantMsg = { role: "assistant", content: "", tools: [], meta: null };
    session.messages.push(assistantMsg);

    let firstToken = true;
    let currentToolPills = null;
    let contentEl = null;

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
        // Remove assistant + user messages (failed before streaming)
        session.messages.pop(); // assistant
        session.messages.pop(); // user
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
        buffer = lines.pop(); // keep incomplete line

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

          // Remove thinking on first real event
          if (firstToken) {
            thinkingEl.remove();
            const msgEl = appendMessageEl("assistant");
            currentToolPills = msgEl.querySelector(".tool-pills");
            contentEl = msgEl.querySelector(".message-body");
            firstToken = false;
          }

          switch (event.type) {
            case "text":
              assistantMsg.content += event.content;
              contentEl.innerHTML = marked.parse(assistantMsg.content);
              scrollToBottom();
              break;

            case "tool_start":
              assistantMsg.tools.push({ name: event.name, status: "running" });
              renderToolPills(currentToolPills, assistantMsg.tools);
              scrollToBottom();
              break;

            case "tool_complete":
              // Mark tool as done
              for (const t of assistantMsg.tools) {
                if (t.name === event.name && t.status === "running") {
                  t.status = "done";
                  break;
                }
              }
              renderToolPills(currentToolPills, assistantMsg.tools);
              break;

            case "tool_input":
              // Ignore streaming tool input for now
              break;

            case "result":
              session.serverSessionId = event.session_id;
              assistantMsg.meta = {
                cost: event.cost_usd,
                turns: event.turns,
                session_id: event.session_id,
              };
              // Update session title from first assistant reply
              if (session.messages.filter(m => m.role === "assistant").length === 1) {
                session.title = assistantMsg.content.slice(0, 60).replace(/\n/g, " ") || session.title;
                renderSessionList();
              }
              break;

            case "error":
              showError(event.message || "An error occurred during streaming.");
              break;
          }
        }
      }

      // Render metadata line
      if (assistantMsg.meta && contentEl) {
        const metaEl = document.createElement("div");
        metaEl.className = "message-meta";
        const parts = [];
        if (assistantMsg.meta.cost != null) parts.push(`$${assistantMsg.meta.cost.toFixed(4)}`);
        if (assistantMsg.meta.turns != null) parts.push(`${assistantMsg.meta.turns} turn${assistantMsg.meta.turns !== 1 ? "s" : ""}`);
        metaEl.textContent = parts.join(" \u00b7 ");
        contentEl.parentElement.appendChild(metaEl);
      }

    } catch (err) {
      if (err.name === "AbortError") {
        console.log("[chat] Request aborted by user");
        // User cancelled — remove empty assistant message
        if (!assistantMsg.content) session.messages.pop();
      } else {
        console.error("[chat] Connection error:", err.message);
        showError("Connection lost. Please try again.");
        // Remove empty assistant message and the user message (never reached server)
        if (!assistantMsg.content) {
          session.messages.pop(); // assistant
          session.messages.pop(); // user
        }
        // Restore the input so user can retry
        messageInput.value = text;
      }
      thinkingEl.remove();
    }

    // If still showing thinking (e.g. empty response), remove it
    if (firstToken) thinkingEl.remove();

    saveSessions();
    streaming = false;
    sendBtn.disabled = !messageInput.value.trim();
    abortController = null;
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
          const metaEl = document.createElement("div");
          metaEl.className = "message-meta";
          const parts = [];
          if (msg.meta.cost != null) parts.push(`$${msg.meta.cost.toFixed(4)}`);
          if (msg.meta.turns != null) parts.push(`${msg.meta.turns} turn${msg.meta.turns !== 1 ? "s" : ""}`);
          metaEl.textContent = parts.join(" \u00b7 ");
          el.appendChild(metaEl);
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

    // Attach click handlers
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
      // localStorage full or unavailable — silent fail
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
})();
