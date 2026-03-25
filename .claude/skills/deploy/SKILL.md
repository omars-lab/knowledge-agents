---
name: deploy
description: Deploy the knowledge-agents stack locally or to the Mac Studio
user_invocable: true
---

# /deploy — Deploy the knowledge-agents stack

Deploy the full knowledge-agents stack locally or to the Mac Studio. Uses git-based sync (never rsync) and auto-detects which machine you're on.

## How to use

```
/deploy           # Deploy to Mac Studio (or locally if already on it)
/deploy local     # Deploy locally on the current machine
/deploy status    # Check container status
/deploy verify    # Post-deploy health checks
/deploy down      # Stop the stack
```

## Workflow

### 1. Ensure hosts.yml exists

`hosts.yml` is gitignored (contains hardware serials). If missing locally, pull it from the Mac Studio:

```bash
if [ ! -f hosts.yml ]; then
  scp mac-studio:~/Workspace/git/knowledge-agents/hosts.yml hosts.yml
fi
```

### 2. Detect the current machine

```bash
system_profiler SPHardwareDataType 2>/dev/null | awk '/Serial Number/ {print $NF}'
cat hosts.yml
```

Cross-reference the serial against `hosts.yml`:
- Serial matching `role: prod` → Mac Studio — deploy runs locally
- Otherwise → dev machine — deploy goes via SSH

### 3. Determine deploy target

Based on the user's argument:

| Argument | Action |
|----------|--------|
| (none) | `make deploy` — pushes to origin, pulls on Mac Studio, starts stack |
| `local` | `make local-deploy` — starts stack locally with `LM_STUDIO_HOST=localhost` |
| `status` | `make deploy-status` — shows container status |
| `verify` | `make verify` — runs full health check suite |
| `down` | `make deploy-down` — stops the stack |
| `logs` | `make deploy-logs` — tails logs |

### 4. For remote deploy (MacBook → Mac Studio)

Pre-flight checks before running `make deploy`:

```bash
# 1. Working tree clean?
git status -s --ignore-submodules

# 2. Branch pushed?
git rev-parse HEAD
git rev-parse origin/$(git rev-parse --abbrev-ref HEAD)

# 3. SSH reachable?
ssh -o ConnectTimeout=5 mac-studio "echo OK"

# 4. Docker running on Mac Studio?
ssh mac-studio "docker info > /dev/null 2>&1 && echo OK"
```

If pre-flight passes, run:
```bash
make deploy
```

This will:
1. Verify clean working tree and branch pushed to origin
2. SSH to Mac Studio and `git pull`
3. Build + start stack with `LM_STUDIO_HOST=localhost`
4. Show container status

### 5. For local deploy

```bash
make local-deploy
```

Starts the full stack with `LM_STUDIO_HOST=localhost` (assumes LM Studio is running on the same machine).

### 6. Post-deploy verification

Always run after deploying:
```bash
make verify
```

Checks 5 categories:
1. **Service health** — knowledge-api (:8001), claude-agent (:8004), tidy-mcp (:8003), litellm (:4000)
2. **Database connectivity** — Qdrant (:6333), Neo4j (:7474), Postgres
3. **LM Studio** — embedding model loaded (:1234)
4. **Container status** — no Restarting/Exit containers
5. **Observability** — Prometheus (:9090), Grafana (:3001), Langfuse (:3210, optional)

### 7. Seed Claude Agent auth

The claude-agent container needs OAuth credentials. On remote deploys the Mac Studio keychain is typically locked, so seed from the MacBook's keychain:

```bash
# Cross-machine seed (MacBook → Mac Studio container)
CREDS=$(security find-generic-password -s 'Claude Code-credentials' -w)
echo "$CREDS" | ssh mac-studio "zsh -l -c 'cat > /tmp/claude_creds.json && \
  docker cp /tmp/claude_creds.json knowledge-agents-claude-agent-1:/home/agent/.claude/.credentials.json && \
  docker exec -u root knowledge-agents-claude-agent-1 chown agent:agent /home/agent/.claude/.credentials.json && \
  rm /tmp/claude_creds.json'"
```

Or if the keychain is unlocked on the Mac Studio: `make claude-agent-auth-seed`

Verify with: `make claude-agent-auth-status`

See `/refresh-auth` for full auth management details.

## Troubleshooting


### 8. Security and cross-stack checks

After deploy and verification, always run:

```bash
# Verify no OOTB credentials are in use
make check-ootb-secrets

# Reconnect Langfuse to private-site network (lost on container recreate)
make langfuse-connect
make langfuse-check
```

Add these to the post-deploy checklist whenever the stack is redeployed.

| Issue | Fix |
|-------|-----|
| `Uncommitted changes` | Commit and push first |
| `Branch not pushed` | `git push` |
| `Cannot reach mac-studio` | Check SSH config and network |
| `Docker not running` on Mac Studio | Start Docker Desktop on Mac Studio |
| `LM Studio` check fails | `make lm-studio-status` and `make lm-studio-load-embeddings` |
| Container unhealthy after deploy | `make deploy-logs` to check errors |
| Env var changes not picked up | `docker compose up -d --force-recreate <service>` (see CLAUDE.md gotcha #9) |
| Claude agent 500 errors | Auth not seeded — use cross-machine seed from MacBook (see step 7) |
| `docker build` fails with keychain error | macOS keychain locked — unlock via Screen Sharing or use cross-machine seed |
| `No valid credentials in Keychain` | Run `claude auth login` on the host, or use cross-machine seed |
| Postgres port conflict | Set `POSTGRES_HOST_PORT=5433` in `.env` on Mac Studio |

## Key Files

- `hosts.yml` — Machine serial → role mapping
- `Makefile` — `deploy`, `local-deploy`, `verify`, `deploy-status`, `deploy-down`, `deploy-logs` targets
- `docker-compose.yml` — Service definitions and port mappings
- `.claude/skills/deploy-llm.md` — LM Studio infrastructure (prerequisite)
- `.claude/skills/refresh-auth.md` — Claude Agent auth management (post-deploy)
