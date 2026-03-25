# Plan: Rich Chat UI at chat.bytesofpurpose.com

## Context

The `knowledge-agents` stack has a `claude-agent` service (multi-turn conversational agent) and supporting infrastructure (Qdrant vectors, Neo4j graphs, seeder/indexer). We want a rich, mobile-friendly chat interface at `chat.bytesofpurpose.com` behind CF Access that provides:

- SSE streaming chat with tool execution indicators
- Inline Mermaid diagrams + interactive force graphs (auto-select by size)
- NotePlan tile cards with xcallback:// links
- Google Maps visualization for places
- Trigger re-indexing (seeder/graph-builder) from the UI
- 2D/3D embedding vector space visualization
- Zero API keys in browser — security model documented in `docs/chat-security-model.md`

### Existing Backend Support

The claude-agent already provides what Phase 1 needs:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /api/v1/chat/stream` | SSE | Token-by-token streaming with tool events |
| `POST /api/v1/chat` | JSON | Buffered full response |
| `GET /api/v1/sessions` | JSON | List all sessions |
| `DELETE /api/v1/sessions/{id}` | — | Close a session |
| `GET /api/v1/sessions/{id}/artifacts` | JSON | List session files |
| `GET /health` | — | Health check |
| `GET /metrics` | — | Prometheus metrics |

Both chat endpoints accept optional `session_id` for multi-turn context. No new backend work needed for Phase 1.

## Repo Split

The chat UI lives in **knowledge-agents** (alongside the claude-agent it depends on). The **private-site** repo only handles routing (Kong, CF Tunnel, DNS).

| Repo | Responsibility |
|------|---------------|
| `knowledge-agents` | `chat/` directory, `chat` container, chat UI code, compose service |
| `private-site` | Kong route for `chat.bytesofpurpose.com`, CF DNS + Tunnel, security model doc |

## Phased Implementation

Given the scope, we'll build in phases — each phase is deployable independently.

### Phase 1: Core Chat + Streaming (next session)

Build the foundational chat page with SSE streaming, deploy to prod.

**New container: `chat`** — nginx container in the knowledge-agents stack serving the chat UI.

**knowledge-agents repo files:**
- `chat/index.html` — Chat UI entry point
- `chat/chat.js` — SSE streaming, session management, message rendering
- `chat/chat.css` — Styles (dark theme)
- `nginx/default.conf` — Nginx health endpoint config (required by healthcheck)
- `docker-compose.yml` — Add `chat` service (nginx:alpine, bind mount `chat/`)
- Makefile — Add `chat-connect` target (cross-network to private-site_internal)

**private-site repo files:**
- `kong/kong.prod.yml` — Routes for `chat.bytesofpurpose.com` (UI -> chat:80, API -> claude-agent:8000)
- `kong/kong.dev.yml` — Dev route for `/chat/`
- CF DNS + Tunnel — `chat.bytesofpurpose.com`
- `docs/chat-security-model.md` — Security model (already created)

**Features:**
- Message input with auto-resize textarea
- SSE streaming via `POST /api/v1/chat/stream` (token-by-token text rendering)
- Multi-turn conversations: client stores and sends `session_id` from first response
- Tool execution indicators (pill badges: "Using read_note...", "Using query_knowledge_graph...")
- Markdown rendering (marked.js CDN)
- Code syntax highlighting (highlight.js CDN)
- Session management: new chat, session list sidebar, localStorage persistence
- Mobile responsive: collapsible sidebar, touch-friendly
- Dark theme matching existing site design
- "Thinking..." indicator between send and first SSE token
- SSE reconnection: detect dropped connections, show error banner, allow manual retry
- Error states: timeout banner, 5xx error display, tool failure indicators
- Rate limit feedback: if agent returns 429, show "Please wait..." with backoff

### Phase 1.5: Server-Side Sessions + Mobile Session UX

Move sessions from localStorage to Postgres. Improve mobile session browsing.

**Backend — claude-agent server changes:**

New table `chat_sessions` in Postgres (via SQLAlchemy):
```sql
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_session_id TEXT,          -- claude SDK session ID
    title TEXT NOT NULL,
    messages JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

New/updated API endpoints on claude-agent:
- `GET /api/v1/sessions` — List sessions (title, created_at, message_count) — **update existing** to query DB instead of filesystem
- `GET /api/v1/sessions/{id}/messages` — Return full message history for a session
- `POST /api/v1/sessions` — Create a new session (optional title)
- `PUT /api/v1/sessions/{id}` — Update session title
- `DELETE /api/v1/sessions/{id}` — Delete session — **update existing** to also remove DB record
- Auto-persist: the stream endpoint appends user + assistant messages to the DB after each turn

Benefits:
- Sessions persist across devices/browsers (no more localStorage-only)
- Chat UI becomes stateless — can open on phone, continue on laptop
- Server is source of truth; client caches for speed but syncs on load

**Frontend — chat.js changes:**

- On load: `GET /api/v1/sessions` to populate sidebar (replace localStorage read)
- On message send: server persists messages (client updates optimistically)
- On session switch: `GET /api/v1/sessions/{id}/messages` to load history
- localStorage becomes a cache layer — fallback if API unreachable
- Remove `saveSessions()` writes to localStorage for message content (keep for UI prefs only)

**Mobile — bottom sheet session picker:**

Replace the sidebar drawer on mobile with a bottom sheet modal card:

```
+---------------------------------------+
| = Chat . bytesofpurpose.com           |
|                                       |
| [message area]                        |
|                                       |
+---------------------------------------+
| Ask about your notes...        [Send] |
+---------------------------------------+
        |  (swipe up or tap menu)
        v
+---------------------------------------+
|  ----  (drag handle)                  |
|                                       |
|  Sessions                    [+ New]  |
|                                       |
|  +------+ +------+ +------+          |
|  |Chat 1| |Chat 2| |Chat 3|   -->    |
|  |What p.| |Goals | |AI no.|          |
|  |2m ago | |1h ago| |yest. |          |
|  +------+ +------+ +------+          |
|                                       |
+---------------------------------------+
```

- Slides up from bottom (half-screen height, draggable to full)
- Session cards in a horizontal scroll strip or vertical list
- Each card shows: title (truncated), time ago, message count
- Tap to switch, swipe left to delete
- Tap outside or swipe down to dismiss
- Desktop keeps the existing sidebar (no change)

### Phase 2: Rich Rendering + Tool Call Details (next session)

Add inline visualizations and Claude-Code-style expandable tool call blocks.

**Tool Call Expandable Blocks (like Claude Code):**

Each tool call renders as a collapsible block with a duration highlight bar:

```
+------------------------------------------------------------------+
| > mcp__notes__query_knowledge_graph               2.3s   $0.0012 |
+------------------------------------------------------------------+
  (click to expand)
  Model: claude-sonnet-4-20250514
  Input:  {"query": "MATCH (n:Entity)..."}     142 tokens
  Output: {"nodes": [...], "edges": [...]}     387 tokens
  Cost:   $0.0012
  Duration: 2.3s
  |████████░░░░░░░░░░| (duration bar relative to total response time)
+------------------------------------------------------------------+
```

Collapsed state shows: tool name, duration, cost.
Expanded state adds: model, input payload (syntax-highlighted JSON), output payload, token counts.

**Backend change needed** — Enrich `tool_complete` SSE event:
```json
{
  "type": "tool_complete",
  "name": "mcp__notes__query_knowledge_graph",
  "input": "{...}",
  "output": "{...}",
  "duration_ms": 2300,
  "input_tokens": 142,
  "output_tokens": 387,
  "cost_usd": 0.0012,
  "model": "claude-sonnet-4-20250514"
}
```

Currently `tool_complete` only has `name` and `input`. The SDK's `StreamEvent` may not expose per-tool token counts directly — may need to track from `message_delta` usage fields or compute from the `ResultMessage` cost breakdown.

**Rich Rendering Features:**
- Mermaid diagrams: detect ```mermaid code blocks, render inline via mermaid.js (**lazy-loaded** — only fetch the 1.5 MB library when a mermaid block is first detected)
- Interactive force graphs: for knowledge graph results (vis-network CDN). **Node threshold is configurable** — default 20 nodes for auto-switch from Mermaid to force graph, with a toggle button so users can switch between views regardless of size
- NotePlan tile cards: styled cards with title, preview text, xcallback:// link button
- Google Maps: embed map with pins when agent returns place data (Google Maps Embed API, no API key needed for simple embeds, or use Leaflet + OpenStreetMap for zero-cost)

### Phase 3: Knowledge Pipeline Management (future session)

Add embedding visualization and indexer control.

**Features:**
- Trigger re-indexing: button to POST to seeder/graph-builder API, show progress/logs via SSE
- Vector space visualization: 2D scatter plot of embeddings (UMAP projection via server-side compute, rendered with plotly.js or deck.gl)
- Click-to-inspect: click embedding point to see source note

---

## Phase 1 Detail (implementing now)

### `chat/` directory structure

```
chat/
  index.html          # Chat UI entry point
  chat.js             # SSE streaming, session management, rendering
  chat.css            # Dark theme styles
  Dockerfile          # nginx:alpine + default.conf
nginx/
  default.conf         # location /health { return 200 "ok"; }
```

```
+-----------------------------------------+
| = Chat . bytesofpurpose.com    [+ New]  |
+---------+-------------------------------+
|Sessions |  Assistant                    |
|         |  Based on your notes, I found |
| Today   |  3 projects related to...     |
| . Chat 1|                              |
| . Chat 2|  [tool] query_knowledge_graph |
|         |                               |
| Earlier |  You                          |
| . Chat 3|  What projects am I working on|
|         |                               |
|         +-------------------------------+
|         | Type a message...       [Send]|
+---------+-------------------------------+
```

Mobile: sidebar hidden, hamburger menu to toggle.

### Docker Compose — `chat` service

**Base (`docker-compose.yml`):**
```yaml
chat:
  image: nginx:alpine
  volumes:
    - ./chat:/usr/share/nginx/html:ro
    - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
  networks:
    - internal
  profiles: [prod]
  healthcheck:
    test: ["CMD", "wget", "-q", "--spider", "http://localhost/health"]
    interval: 30s
    timeout: 5s
    retries: 3
```

**Dev overlay (`docker-compose.dev.yml`):**
```yaml
chat:
  profiles: []  # Always start in dev
  volumes:
    - ./chat:/usr/share/nginx/html:ro
    - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
```

### Kong Routes

**Prod (`kong.prod.yml`):**
```yaml
- name: chat-ui
  url: http://chat:80
  routes:
    - name: chat-ui-route
      hosts: [chat.bytesofpurpose.com]
      paths: [/]
      strip_path: false

- name: chat-api
  url: http://claude-agent:8000
  routes:
    - name: chat-api-route
      hosts: [chat.bytesofpurpose.com]
      paths: [/api]
      strip_path: false
    - name: chat-health-route
      hosts: [chat.bytesofpurpose.com]
      paths: [/health]
      strip_path: false
```

**Dev (`kong.dev.yml`):** Add path-based route `/chat/` -> `chat:80`.

**Rate limiting (Kong plugin):** Add rate-limiting plugin on the `chat-api` service — e.g., 10 requests/minute per IP. Prevents a single user from hammering the Claude API through the agent. Can be tuned later.

### Cross-Network Docker Connection (same pattern as Langfuse)

Both the `chat` and `claude-agent` containers from knowledge-agents join `private-site_internal`:

```bash
# In knowledge-agents Makefile (new targets):
chat-connect:        ## Connect chat UI to private-site network
	docker network connect --alias chat private-site_internal knowledge-agents-chat-1

claude-agent-connect: ## Connect claude-agent to private-site network
	docker network connect --alias claude-agent private-site_internal knowledge-agents-claude-agent-1

chat-check:          ## Verify chat reachable from private-site
	docker exec private-site-kong-1 ... http://chat:80/health

claude-agent-check:  ## Verify claude-agent reachable from private-site
	docker exec private-site-mcp-1 python3 -c "import urllib.request; ..."
```

Both need `HOSTNAME: 0.0.0.0` in their compose env (Next.js/nginx — nginx is fine by default but document the pattern).

**Connection lost on container recreate** — same gotcha as Langfuse. Post-deploy must run `make chat-connect && make claude-agent-connect`.

### Security Considerations

1. **CF Access JWT validation** — CF Access gates the page and API calls. Consider having claude-agent validate the `Cf-Access-Jwt-Assertion` header server-side as a defense-in-depth measure — without it, anything on the Docker network can call the agent directly. This can be Phase 1 or deferred, but document the risk.

2. **No CORS needed** — Both UI and API are served under `chat.bytesofpurpose.com` via Kong path routing (UI at `/`, API at `/api`). Same origin, no CORS headers required. Verify this works end-to-end during deployment.

3. **Rate limiting** — Kong rate-limiting plugin on the `chat-api` service (see Kong Routes section above).

### Cloudflare Setup

- DNS CNAME: `chat.bytesofpurpose.com` -> tunnel (CF API)
- Tunnel ingress: add `chat.bytesofpurpose.com` -> `http://kong:8000` before catch-all
- CF Access: covered by `*.bytesofpurpose.com` wildcard

### Documentation Updates

- **`docs/ARCHITECTURE.md`** (new, living document) — Mermaid architecture diagram showing all services, containers, networks, and external routing. Added to CLAUDE.md living documents list. Update whenever containers, networks, or routing changes.
- CLAUDE.md: add `docs/ARCHITECTURE.md` to living documents table, update key commands with chat targets
- `docs/site-map.md`: chat hostname mapping
- `docs/cloudflare-setup-log.md`: DNS + tunnel entries
- `docs/chat-security-model.md`: already created

### CDN Libraries (Phase 1)

| Library | Size | Purpose |
|---------|------|---------|
| marked.js | 40 KB | Markdown -> HTML |
| highlight.js | 40 KB | Code syntax highlighting |

Phase 2 adds: mermaid.js (1.5 MB, **lazy-loaded**), vis-network (200 KB), Leaflet (40 KB)

---

## Implementation Order (Phase 1)

**In knowledge-agents repo:**
1. Create `nginx/default.conf` with health endpoint location block
2. Create `chat/` directory with `index.html`, `chat.js`, `chat.css`
3. Implement SSE client connecting to `POST /api/v1/chat/stream` with `session_id` support
4. Implement error handling: thinking indicator, SSE reconnection, timeout/5xx banners, tool failure display
5. Add `chat` service to `docker-compose.yml`
6. Add Makefile targets: `chat-connect`, `chat-check`, `claude-agent-connect`, `claude-agent-check`
7. Integrate `chat-connect` and `claude-agent-connect` into `make deploy` post-deploy steps (same as Langfuse pattern)
8. Create `docs/ARCHITECTURE.md` — Mermaid diagram of full stack (containers, networks, routing)
9. Add `docs/ARCHITECTURE.md` to CLAUDE.md living documents list
10. Deploy knowledge-agents stack on Mac Studio

**In private-site repo (routing only):**
11. Add Kong routes for `chat.bytesofpurpose.com` (`kong.prod.yml` + `kong.dev.yml`)
12. Add Kong rate-limiting plugin on `chat-api` service
13. Add CF DNS + Tunnel ingress via CF API
14. Connect chat + claude-agent to `private-site_internal` network
15. Update portal page with chat card
16. Update docs (site-map, cloudflare-setup-log)
17. Deploy private-site (Kong restart)

## Verification

1. `https://chat.bytesofpurpose.com/` loads behind CF Access
2. Type message -> SSE stream, tool indicators, text appears token-by-token
3. "Thinking..." indicator shows between send and first token
4. Multi-turn: follow-up uses same session (verify `session_id` sent in request)
5. Error handling: disconnect WiFi mid-stream -> error banner with retry button
6. Refresh: session persists (sidebar shows history)
7. Mobile: responsive layout, drawer sidebar
8. DevTools: no API keys in Network tab, localStorage, or JS source
9. Unauthenticated: CF Access redirect (not chat page)
10. Rate limit: rapid-fire 15 messages -> Kong returns 429 after limit
11. `docs/ARCHITECTURE.md` diagram matches deployed state
