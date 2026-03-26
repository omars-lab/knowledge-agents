/* ── Demo Mode ────────────────────────────────────────────────────────── */
/* Replays a mock SSE conversation exercising every card type.           */
/* Activate: http://localhost:8080/?demo=true                            */

export async function runDemo(handleEvent) {
  const events = [
    // ── User message injected by chat.js before calling runDemo ──

    // ── Tool 1: semantic_search → note_cards (all note types) ──────
    { delay: 300, event: { type: "tool_start", name: "semantic_search" } },
    { delay: 1500, event: {
      type: "tool_complete", name: "semantic_search", input: '{"query": "goals", "limit": 6}',
      duration_ms: 1420,
      structured: {
        card_type: "note_cards",
        data: [
          {
            file_path: "Calendar/20260325.md",
            title: "Tuesday, March 25, 2026",
            note_type: "daily",
            preview: "Morning standup: reviewed Q2 goals with the team. Chat UI Phase 1 shipped. Started planning rich card types for the frontend...",
            xcallback_url: "noteplan://x-callback-url/openNote?noteDate=20260325",
            similarity_score: 0.95,
            modified_at: "2026-03-25T10:30:00Z",
            folder: "Calendar",
            tags: [],
            task_stats: { done: 3, total: 5 }
          },
          {
            file_path: "Calendar/2026-W13.md",
            title: "Week 13: Mar 24 - Mar 30, 2026",
            note_type: "weekly",
            preview: "Focus areas: ship chat UI, wire Loki logging, plan rich card types. Review Graphiti integration progress...",
            xcallback_url: "noteplan://x-callback-url/openNote?noteDate=2026-W13",
            similarity_score: 0.91,
            modified_at: "2026-03-24T08:00:00Z",
            folder: "Calendar",
            tags: [],
            task_stats: { done: 5, total: 8 }
          },
          {
            file_path: "\u{1F3E1} Personal/\u{1F3E1}\u{1F4C6} Plans/Present/\u{1F4BB} Software Dev/\u{1F3E1}260325\u{1F4BB} Chat UI Plan.md",
            title: "Chat UI Implementation Plan",
            note_type: "plan",
            preview: "Phase 1: Core chat + streaming. Phase 2: Rich rendering + tool call details. Phase 3: Knowledge pipeline management...",
            xcallback_url: "noteplan://x-callback-url/openNote?filename=%F0%9F%8F%A1%20Personal%2F%F0%9F%8F%A1%F0%9F%93%86%20Plans%2FPresent%2F%F0%9F%92%BB%20Software%20Dev%2F%F0%9F%8F%A1260325%F0%9F%92%BB%20Chat%20UI%20Plan.md",
            similarity_score: 0.92,
            modified_at: "2026-03-25T14:00:00Z",
            folder: "\u{1F3E1} Personal/\u{1F4C6} Plans/\u{1F4BB} Software Dev",
            tags: ["chat-ui", "project"],
            task_stats: { done: 8, total: 12 }
          },
          {
            file_path: "@Templates/\u{1F3E1}\u{1F4C6} Personal Plan.md",
            title: "Personal Plan Template",
            note_type: "template",
            preview: "## What went well?\n\n## What didn't go well?\n\n## Action items for next week\n\n## Gratitude",
            xcallback_url: "noteplan://x-callback-url/openNote?filename=%40Templates%2F%F0%9F%8F%A1%F0%9F%93%86%20Personal%20Plan.md",
            similarity_score: null,
            modified_at: null,
            folder: "@Templates",
            tags: ["template", "review"],
            task_stats: null
          },
          {
            file_path: "\u{1F3E1} Personal/\u{1F4DD} Notes/Q2 OKRs.md",
            title: "Q2 OKRs - Engineering Team",
            note_type: "quip",
            preview: "Objective 1: Ship knowledge-agents v2. KR1: Chat UI deployed to prod. KR2: 95% uptime. KR3: <2s p99 latency...",
            xcallback_url: "noteplan://x-callback-url/openNote?filename=%F0%9F%8F%A1%20Personal%2F%F0%9F%93%9D%20Notes%2FQ2%20OKRs.md",
            quip_url: "https://company.quip.com/abc123/Q2-Engineering-OKRs",
            similarity_score: 0.87,
            modified_at: "2026-03-22T16:45:00Z",
            folder: "\u{1F3E1} Personal/\u{1F4DD} Notes",
            tags: ["okrs", "q2"],
            task_stats: null
          },
          {
            file_path: "\u{1F3E1} Personal/\u{1F3E1}\u{1F4C6} Plans/Present/\u{1F331} Growth/\u{1F3E1}260207\u{1F4DA} Goals.md",
            title: "Goals",
            note_type: "note",
            preview: "My 2026 goals include shipping the knowledge-agents chat UI, completing the graph pipeline, improving personal productivity...",
            xcallback_url: "noteplan://x-callback-url/openNote?filename=%F0%9F%8F%A1%20Personal%2F%F0%9F%8F%A1%F0%9F%93%86%20Plans%2FPresent%2F%F0%9F%8C%B1%20Growth%2F%F0%9F%8F%A1260207%F0%9F%93%9A%20Goals.md",
            similarity_score: 0.93,
            modified_at: "2026-03-20T10:30:00Z",
            folder: "\u{1F3E1} Personal/\u{1F4C6} Plans/\u{1F331} Growth",
            tags: ["goals", "2026"],
            task_stats: null
          }
        ]
      }
    }},

    // ── Text: agent summary after search ───────────────────────────
    ...tokenize("I found 6 notes related to goals across your daily notes, plans, and reference docs. Let me check the knowledge graph for connections between them.", 30),

    // ── Tool 2: query_knowledge_graph → graph ──────────────────────
    { delay: 400, event: { type: "tool_start", name: "query_knowledge_graph" } },
    { delay: 2000, event: {
      type: "tool_complete", name: "query_knowledge_graph", input: '{"query": "goals and projects"}',
      duration_ms: 1870,
      structured: {
        card_type: "graph",
        data: {
          nodes: [
            { id: "1", name: "Goals", type: "Topic", color: "#9B59B6", properties: {} },
            { id: "2", name: "Ship Chat UI", type: "Task", color: "#E67E22", properties: { status: "active" } },
            { id: "3", name: "Knowledge Agents", type: "Project", color: "#50C878", properties: {} },
            { id: "4", name: "Omar", type: "Person", color: "#4A90D9", properties: {} },
            { id: "5", name: "Q2 OKRs", type: "Topic", color: "#9B59B6", properties: {} },
            { id: "6", name: "Graph Pipeline", type: "Task", color: "#E67E22", properties: { status: "in-progress" } },
            { id: "7", name: "Productivity", type: "Topic", color: "#9B59B6", properties: {} },
            { id: "8", name: "2026", type: "Date", color: "#F39C12", properties: {} },
            { id: "9", name: "LM Studio", type: "Tool", color: "#1ABC9C", properties: {} },
            { id: "10", name: "Graphiti", type: "Tool", color: "#1ABC9C", properties: {} },
            { id: "11", name: "Mac Studio", type: "Tool", color: "#1ABC9C", properties: {} },
            { id: "12", name: "Austin, TX", type: "Location", color: "#E74C3C", properties: {} }
          ],
          edges: [
            { source: "1", target: "2", type: "HAS_GOAL", label: "HAS_GOAL" },
            { source: "1", target: "6", type: "HAS_GOAL", label: "HAS_GOAL" },
            { source: "1", target: "7", type: "RELATES_TO", label: "RELATES_TO" },
            { source: "2", target: "3", type: "PART_OF", label: "PART_OF" },
            { source: "4", target: "3", type: "WORKS_ON", label: "WORKS_ON" },
            { source: "4", target: "1", type: "AUTHORED", label: "AUTHORED" },
            { source: "3", target: "9", type: "USES", label: "USES" },
            { source: "3", target: "10", type: "USES", label: "USES" },
            { source: "6", target: "10", type: "DEPENDS_ON", label: "DEPENDS_ON" },
            { source: "5", target: "2", type: "INCLUDES", label: "INCLUDES" },
            { source: "5", target: "6", type: "INCLUDES", label: "INCLUDES" },
            { source: "3", target: "8", type: "CREATED_IN", label: "CREATED_IN" },
            { source: "4", target: "12", type: "LOCATED_IN", label: "LOCATED_IN" },
            { source: "11", target: "9", type: "HOSTS", label: "HOSTS" }
          ]
        }
      }
    }},

    // ── Text: graph analysis with mermaid diagram ─────────────────
    // Send mermaid block as a single text event to avoid partial parsing
    { delay: 50, event: { type: "text", content: "Here's how your goals connect:\n\n```mermaid\ngraph LR\n    Goals -->|HAS_GOAL| ShipChatUI[Ship Chat UI]\n    Goals -->|HAS_GOAL| GraphPipeline[Graph Pipeline]\n    Goals -->|RELATES_TO| Productivity\n    ShipChatUI -->|PART_OF| KnowledgeAgents[Knowledge Agents]\n    GraphPipeline -->|DEPENDS_ON| Graphiti\n    Omar -->|WORKS_ON| KnowledgeAgents\n    Q2OKRs[Q2 OKRs] -->|INCLUDES| ShipChatUI\n    Q2OKRs -->|INCLUDES| GraphPipeline\n```\n\n" } },
    ...tokenize("The **Goals** topic links to two active tasks: **Ship Chat UI** and **Graph Pipeline**, both part of the **Knowledge Agents** project. Your Q2 OKRs reference both tasks.", 40),

    // ── Tool 3: derive links → links (all link types) ─────────────
    { delay: 300, event: { type: "tool_start", name: "derive_xcallback_url" } },
    { delay: 500, event: {
      type: "tool_complete", name: "derive_xcallback_url", input: '{"file_path": "Notes/Goals.md"}',
      duration_ms: 120,
      structured: {
        card_type: "links",
        data: [
          { url: "noteplan://x-callback-url/openNote?filename=%F0%9F%8F%A1%20Personal%2F%F0%9F%8F%A1%F0%9F%93%86%20Plans%2FPresent%2F%F0%9F%8C%B1%20Growth%2F%F0%9F%8F%A1260207%F0%9F%93%9A%20Goals.md", type: "noteplan", label: "\u{1F4DA} Goals.md" },
          { url: "https://company.quip.com/abc123/Q2-Engineering-OKRs", type: "quip", label: "Q2 OKRs" },
          { url: "vscode://file/Users/omareid/Workspace/git/knowledge-agents/src/knowledge_agents/claude_agent/server.py", type: "vscode", label: "server.py" },
          { url: "https://github.com/omars-lab/knowledge-agents", type: "github", label: "knowledge-agents" },
          { url: "mailto:omar@example.com", type: "email", label: "omar@example.com" },
          { url: "https://maps.google.com/?q=Austin,TX", type: "location", label: "Austin, TX" },
          { url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ", type: "web", label: "Knowledge Graph Talk" }
        ]
      }
    }},

    // ── Text + file card ───────────────────────────────────────────
    ...tokenize("Here are all the relevant links. I also found a reference to the agent server code:", 25),

    // ── Inline file card ───────────────────────────────────────────
    { delay: 200, event: {
      type: "tool_complete", name: "read_note", input: '{"file_path": "src/knowledge_agents/claude_agent/server.py"}',
      duration_ms: 85,
      structured: {
        card_type: "note_cards",
        data: [{
          file_path: "src/knowledge_agents/claude_agent/server.py",
          title: "server.py",
          note_type: "file",
          preview: "FastAPI server for the Claude Agent service. Endpoints: health, chat, stream, sessions, artifacts, metrics.",
          vscode_url: "vscode://file/Users/omareid/Workspace/git/knowledge-agents/src/knowledge_agents/claude_agent/server.py",
          language: "Python",
          similarity_score: null,
          modified_at: "2026-03-25T15:00:00Z",
          folder: "src/knowledge_agents/claude_agent",
          tags: [],
          task_stats: null
        }]
      }
    }},

    // ── Tool 4: changelog → timeline ───────────────────────────────
    { delay: 400, event: { type: "tool_start", name: "knowledge_changelog" } },
    { delay: 1200, event: {
      type: "tool_complete", name: "knowledge_changelog", input: '{"start_date": "2026-03-17", "end_date": "2026-03-24"}',
      duration_ms: 1150,
      structured: {
        card_type: "changelog",
        data: {
          start_date: "2026-03-17",
          end_date: "2026-03-24",
          entries: [
            { date: "2026-03-25", action: "new", summary: "Chat UI Phase 1 shipped", entity: "Project" },
            { date: "2026-03-25", action: "new", summary: "Loki logging pipeline wired", entity: "Infrastructure" },
            { date: "2026-03-24", action: "new", summary: "Qwen3.5-9B selected for summarization", entity: "Model Decision" },
            { date: "2026-03-24", action: "updated", summary: "LM Studio models", detail: "Added eval results and comparison" },
            { date: "2026-03-22", action: "new", summary: "Chat UI plan created", entity: "Plan" },
            { date: "2026-03-20", action: "new", summary: "Graphiti integration started", entity: "Feature" },
            { date: "2026-03-19", action: "deleted", summary: "Old auth middleware removed", detail: "Replaced by CF Access" },
            { date: "2026-03-17", action: "updated", summary: "Secrets policy enforced", detail: "All secrets moved to .env" }
          ]
        }
      }
    }},

    // ── Final text ─────────────────────────────────────────────────
    ...tokenize("Here's your knowledge changelog for the past week. You've been productive — Chat UI shipped, logging wired up, and model selection finalized!", 25),

    // ── Result ─────────────────────────────────────────────────────
    { delay: 200, event: {
      type: "result",
      session_id: "demo-session-001",
      cost_usd: 0.0349,
      turns: 2,
      duration_ms: 8500
    }}
  ];

  for (const { delay, event } of events) {
    await sleep(delay);
    handleEvent(event);
  }
}

// ── Helpers ────────────────────────────────────────────────────────────

function tokenize(text, chunkSize) {
  const events = [];
  for (let i = 0; i < text.length; i += chunkSize) {
    events.push({
      delay: 50,
      event: { type: "text", content: text.slice(i, i + chunkSize) }
    });
  }
  return events;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
