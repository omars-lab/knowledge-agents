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
- `docker-compose.yml` — Add `chat` service (nginx:alpine, bind mount `chat/`)
- Makefile — Add `chat-connect` target (cross-network to private-site_internal)

**private-site repo files:**
- `kong/kong.prod.yml` — Routes for `chat.bytesofpurpose.com` (UI → chat:80, API → claude-agent:8000)
- `kong/kong.dev.yml` — Dev route for `/chat/`
- CF DNS + Tunnel — `chat.bytesofpurpose.com`
- `docs/chat-security-model.md` — Security model (already created)

**Features:**
- Message input with auto-resize textarea
- SSE streaming (token-by-token text rendering)
- Tool execution indicators (pill badges: "Using read_note...", "Using query_knowledge_graph...")
- Markdown rendering (marked.js CDN)
- Code syntax highlighting (highlight.js CDN)
- Session management: new chat, session list sidebar, localStorage persistence
- Mobile responsive: collapsible sidebar, touch-friendly
- Dark theme matching existing site design

### Phase 2: Rich Rendering (next session)

Add inline visualizations for agent responses.

**Features:**
- Mermaid diagrams: detect ```mermaid code blocks, render inline via mermaid.js
- Interactive force graphs: for knowledge graph results ≥20 nodes (vis-network CDN)
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
  Dockerfile          # nginx:alpine + health.conf
```

```
┌──────────────────────────────────────────┐
│ ☰ Chat · bytesofpurpose.com    [+ New]   │
├─────────┬────────────────────────────────┤
│Sessions │  Assistant                     │
│         │  Based on your notes, I found  │
│ Today   │  3 projects related to...      │
│ • Chat 1│                                │
│ • Chat 2│  🔧 Using query_knowledge_graph│
│         │                                │
│ Earlier │  You                           │
│ • Chat 3│  What projects am I working on?│
│         │                                │
│         ├────────────────────────────────┤
│         │ Type a message...        [Send]│
└─────────┴────────────────────────────────┘
```

Mobile: sidebar hidden, hamburger menu to toggle.

### Docker Compose — `chat` service

**Base (`docker-compose.yml`):**
```yaml
chat:
  image: nginx:alpine
  volumes:
    - ./chat:/usr/share/nginx/html:ro
    - ./nginx/health.conf:/etc/nginx/conf.d/health.conf:ro
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
    - ./nginx/health.conf:/etc/nginx/conf.d/health.conf:ro
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

**Dev (`kong.dev.yml`):** Add path-based route `/chat/` → `chat:80`.

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

### Cloudflare Setup

- DNS CNAME: `chat.bytesofpurpose.com` → tunnel (CF API)
- Tunnel ingress: add `chat.bytesofpurpose.com` → `http://kong:8000` before catch-all
- CF Access: covered by `*.bytesofpurpose.com` wildcard

### Documentation Updates

- CLAUDE.md: architecture diagram, routing table, living docs table
- `docs/site-map.md`: chat hostname mapping
- `docs/cloudflare-setup-log.md`: DNS + tunnel entries
- `docs/chat-security-model.md`: already created

### CDN Libraries (Phase 1)

| Library | Size | Purpose |
|---------|------|---------|
| marked.js | 40 KB | Markdown → HTML |
| highlight.js | 40 KB | Code syntax highlighting |

Phase 2 adds: mermaid.js (1.5 MB), vis-network (200 KB), Leaflet (40 KB)

---

## Implementation Order (Phase 1)

**In knowledge-agents repo (switch dir to build):**
1. Create `chat/` directory with `index.html`, `chat.js`, `chat.css`
2. Add `chat` service to `docker-compose.yml`
3. Add Makefile targets: `chat-connect`, `chat-check`, `claude-agent-connect`, `claude-agent-check`
4. Deploy knowledge-agents stack on Mac Studio

**In private-site repo (routing only):**
5. Add Kong routes for `chat.bytesofpurpose.com` (`kong.prod.yml` + `kong.dev.yml`)
6. Add CF DNS + Tunnel ingress via CF API
7. Connect chat + claude-agent to `private-site_internal` network
8. Update portal page with chat card
9. Update docs (CLAUDE.md, site-map, cloudflare-setup-log)
10. Deploy private-site (Kong restart)
3. Connect claude-agent to `private-site_internal` network + Makefile targets
4. Add CF DNS + Tunnel ingress
5. Add chat card to `site/index.html` portal
6. Update docs (CLAUDE.md, site-map, cloudflare-setup-log)
7. Commit, deploy, verify

## Verification

1. `https://chat.bytesofpurpose.com/chat/` loads behind CF Access
2. Type message → SSE stream, tool indicators, text appears token-by-token
3. Multi-turn: follow-up uses same session
4. Refresh: session persists (sidebar shows history)
5. Mobile: responsive layout, drawer sidebar
6. DevTools: no API keys in Network tab, localStorage, or JS source
7. Unauthenticated: CF Access redirect (not chat page)
