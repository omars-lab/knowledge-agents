# Session Prompt: Private-Site Chat Routing

> Copy-paste this into a Claude Code session in the `private-site` repo to set up routing for `chat.bytesofpurpose.com`.

---

## Context

The `knowledge-agents` repo now has a `chat` container (nginx:alpine serving static chat UI) and the existing `claude-agent` container (FastAPI on port 8000). Both need to be routable from the internet via Kong and CF Tunnel in the private-site stack.

The chat UI is served at `chat.bytesofpurpose.com` — the UI static files come from the `chat` container and API calls go to `claude-agent`. Both containers will be connected to `private-site_internal` Docker network (same pattern as Langfuse).

The full chat UI plan is at: `../knowledge-agents/.claude/plans/chat-ui-plan.md`

## Tasks

### 1. Kong Routes — `kong/kong.prod.yml`

Add two new services after the Langfuse block, following the existing pattern:

```yaml
  # ── Chat UI (external: knowledge-agents stack) ──────────────────────────
  - name: chat-ui
    url: http://chat:80
    routes:
      - name: chat-ui-route
        hosts: [chat.bytesofpurpose.com]
        paths: [/]
        strip_path: false

  # ── Chat API (external: knowledge-agents stack) ─────────────────────────
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

Also add a rate-limiting plugin scoped to the `chat-api` service in the `plugins:` section:

```yaml
  # ── Rate limit chat API ───────────────────────────────────────────────
  - name: rate-limiting
    service: chat-api
    config:
      minute: 10
      policy: local
      fault_tolerant: true
      hide_client_headers: false
```

### 2. Kong Dev Routes — `kong/kong.dev.yml`

Add path-based dev route for local testing:

```yaml
  - name: chat-ui
    url: http://chat:80
    routes:
      - name: chat-ui-route
        paths: [/chat]
        strip_path: true

  - name: chat-api
    url: http://claude-agent:8000
    routes:
      - name: chat-api-route
        paths: [/chat/api]
        strip_path: false
```

### 3. Cloudflare DNS + Tunnel

Add `chat.bytesofpurpose.com` to the CF Tunnel ingress. The tunnel token is in `.env`. Use the CF API or dashboard:

- **DNS**: CNAME `chat` -> tunnel UUID (same as other subdomains)
- **Tunnel ingress**: `chat.bytesofpurpose.com` -> `http://kong:8000` (add before the catch-all rule)
- **CF Access**: Already covered by `*.bytesofpurpose.com` wildcard application

Document the new entries in `docs/cloudflare-setup-log.md`.

### 4. Portal Card — `site/index.html`

Add a chat card to the services grid. Insert it as the first card (most useful service). Follow the existing card pattern:

```html
    <a href="https://chat.bytesofpurpose.com" class="service-card" style="--card-accent: #a78bfa">
      <div class="service-info">
        <span class="service-title">Chat <span class="badge badge--auth">Sign in</span></span>
        <span class="service-desc">Ask questions about your notes, projects, and knowledge graph</span>
      </div>
      <span class="service-meta">&rarr;</span>
    </a>
```

### 5. Update `docs/site-map.md`

Add the new hostname mapping:

```
| chat.bytesofpurpose.com | Chat UI + Knowledge Agent API | knowledge-agents stack (chat + claude-agent containers) |
```

### 6. Update `docs/chat-security-model.md`

This file already exists. Review it and update if needed to reflect:
- Kong rate-limiting on the API
- No CORS needed (same-origin via Kong path routing)
- CF Access JWT validation is defense-in-depth (not yet enforced server-side)

### 7. Deploy

```bash
make deploy          # or docker compose up -d
# Then in knowledge-agents repo:
make chat-connect && make claude-agent-connect
# Verify:
make verify          # or curl https://chat.bytesofpurpose.com/health
```

### 8. Commit

Commit message: `Add chat.bytesofpurpose.com routing: Kong routes, CF DNS, portal card`
