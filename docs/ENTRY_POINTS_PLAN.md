# Knowledge Agent Entry Points Plan

## Current Entry Points

| Entry Point | Type | Status |
|---|---|---|
| REST API (`localhost:8004`) | On-demand | Working |
| Claude Code `/knowledge` skill | On-demand (via curl) | Working |
| `make claude-agent-chat MSG="..."` | CLI one-liner | Working |
| Makefile targets (graph, eval, etc.) | CLI | Working |

**No event-driven, scheduled, or automated triggers exist yet.**

---

## Planned Entry Points

### 1. File Watcher — Auto-index on NotePlan Changes

- **Trigger:** File watcher (fsevents on macOS) on the NotePlan directory
- **Action:** Index new/changed notes into Qdrant + build knowledge graph incrementally
- **Value:** Knowledge graph stays fresh without manual `make seed-sections`
- **Concern:** NotePlan saves frequently (every keystroke?), so we need debouncing — only process after N seconds of no changes
- **Implementation:** Python `watchdog` library or a launchd plist watching the folder
- **Priority:** High — biggest bang for buck

### 2. Apple Shortcuts

- **Trigger:** Siri, Share Sheet, widget, or manual shortcut
- **Action:** Hit the REST API at `localhost:8004/api/v1/chat`
- **Value:** "Hey Siri, what did I write about X?" — query notes from anywhere on the Mac/iPhone
- **Concern:** Only works when Docker stack is running locally. No remote access unless we expose the API (security implications)
- **Implementation:** Simple Shortcut with "Get Contents of URL" action → POST to the chat endpoint
- **Priority:** High — low effort, high convenience

### 3. Scheduled/Cron (Background Maintenance)

- **Trigger:** launchd plist or cron
- **Action:** Periodic re-index, graph enrichment, stale session cleanup
- **Value:** "Every night, re-index today's notes and update the knowledge graph"
- **Concern:** Needs the Docker stack running. Could use `make seed-sections` as the cron target
- **Implementation:** launchd plist on macOS, or a lightweight scheduler container
- **Priority:** Medium — simple and reliable

### 4. Dedicated Chat Interface

- **Options:** Simple web UI (htmx/React), native macOS menu bar app, or terminal TUI
- **Value:** Richer experience than curl — see streaming responses, session history, graph visualizations inline
- **Concern:** Scope creep — is this worth building vs. just using Claude Code?
- **Implementation:** The `/api/v1/chat/stream` SSE endpoint already exists, so a frontend just needs to consume it
- **Priority:** Low — Claude Code already fills this role

### 5. NotePlan Plugin / x-callback-url Reverse

- **Trigger:** From within NotePlan itself — a plugin button or template command
- **Action:** Send the current note to the agent for analysis, summarization, or graph building
- **Value:** "Analyze this note" without leaving NotePlan
- **Concern:** NotePlan plugin API is JavaScript-based with its own constraints
- **Implementation:** NotePlan plugin calling the REST API
- **Priority:** Low — most effort, most integration friction

## Implementation Order

1. File watcher (keeps knowledge graph fresh automatically)
2. Apple Shortcut (low effort, high convenience)
3. Scheduled cron (nightly re-index)
4. Chat UI (nice-to-have)
5. NotePlan plugin (most effort)
