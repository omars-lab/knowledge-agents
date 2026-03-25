---
name: refresh-auth
description: Refresh Claude Agent container OAuth tokens from macOS Keychain
user_invocable: true
---

# /refresh-auth — Refresh Claude Agent container authentication

Manage Claude CLI authentication for the containerized Claude Agent service.

## How Auth Works

The Claude Agent container runs `@anthropic-ai/claude-code` CLI as a subprocess (via `claude-agent-sdk`). The CLI needs OAuth credentials to call the Anthropic API.

### Token Storage Chain
1. **Host**: Claude Code stores OAuth tokens in **macOS Keychain** under service `Claude Code-credentials`
2. **Keychain entry format**: JSON with `claudeAiOauth` object containing `accessToken`, `refreshToken`, `expiresAt`, `scopes`, `subscriptionType`, `rateLimitTier`
3. **Container**: The CLI falls back to `~/.claude/.credentials.json` when no keychain is available
4. **Persistence**: The container's `~/.claude` is a Docker named volume (`claude_agent_config`) — survives restarts

### Token Lifecycle
- OAuth tokens have an `expiresAt` field (epoch milliseconds)
- Tokens typically expire in **6-24 hours**
- The CLI may auto-refresh using the `refreshToken` if the token is close to expiry
- When tokens expire, agent queries return `CLIConnectionError`

## Refresh Methods

### Method 1: Seed from Host Keychain (fastest, no browser)
```bash
make claude-agent-auth-seed
```
Extracts the OAuth token from the host's macOS Keychain (`security find-generic-password -s "Claude Code-credentials" -w`) and writes it to the container's `.credentials.json`. Requires the host to be logged in.

### Method 2: Interactive Login (if host token expired)
```bash
make claude-agent-login
```
Opens the Claude OAuth flow inside the container — produces a browser URL to visit. The token is stored directly in the container's named volume.

### Method 3: Cross-machine seed (MacBook → Mac Studio)

When deploying to the Mac Studio, the keychain may be locked (no GUI session). Seed from the MacBook's keychain instead:

```bash
# Extract creds from MacBook keychain, pipe to Mac Studio container
CREDS=$(security find-generic-password -s 'Claude Code-credentials' -w)
echo "$CREDS" | ssh mac-studio "zsh -l -c 'cat > /tmp/claude_creds.json && \
  docker cp /tmp/claude_creds.json knowledge-agents-claude-agent-1:/home/agent/.claude/.credentials.json && \
  docker exec -u root knowledge-agents-claude-agent-1 chown agent:agent /home/agent/.claude/.credentials.json && \
  rm /tmp/claude_creds.json'"
```

This works because OAuth tokens are not machine-specific — the same token works from any host.

### Method 4: API Key (no OAuth, pay-as-you-go billing)
Set `ANTHROPIC_API_KEY` in `.env` and it's passed to the container via docker-compose. This bypasses OAuth entirely but uses API billing instead of subscription.

## Unlocking the macOS Keychain via SSH

The keychain locks when no GUI session is active. To unlock it remotely:

```bash
# Interactive — will prompt for password
ssh mac-studio "security unlock-keychain ~/Library/Keychains/login.keychain-db"
```

If the keychain is locked, `make claude-agent-auth-seed` and `docker build` (which uses Docker credential helpers) will both fail. Options:
1. VNC/Screen Sharing to the Mac Studio to unlock
2. Use the cross-machine seed method (Method 3) from the MacBook
3. Set `ANTHROPIC_API_KEY` in `.env` to bypass OAuth entirely

## Check Status
```bash
make claude-agent-auth-status
```
Shows:
- Auth method and login status (via `claude auth status --json`)
- Token expiry countdown (via `scripts/check_claude_auth_expiry.py`)
- Subscription type and rate limit tier

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `CLIConnectionError: ProcessTransport is not ready` | Expired/missing token | `make claude-agent-auth-seed` |
| `loggedIn: false` in auth status | No `.credentials.json` in volume | `make claude-agent-auth-seed` or `make claude-agent-login` |
| Token expires in < 1 hour | Normal token rotation | `make claude-agent-auth-seed` to get fresh token from host |
| `Permission denied` on `.credentials.json` | Volume created as root | `docker exec -u root <container> chown -R agent:agent /home/agent/.claude` |
| Host keychain returns < 50 chars | Placeholder key in keychain | Run `claude auth login` on the host first |

## Key Files
- `scripts/check_claude_auth_expiry.py` — Token expiry checker
- `docker-compose.yml` — `claude_agent_config` named volume mount
- `Dockerfile` — `claude-agent` stage with Node.js + Claude CLI installed
- `Makefile` — `claude-agent-login`, `claude-agent-auth-seed`, `claude-agent-auth-status` targets
