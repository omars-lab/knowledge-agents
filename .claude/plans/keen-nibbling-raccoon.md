# Fix ~60s CLI Subprocess Timeout for Complex Tool Queries

## Context

The Claude Agent SDK's CLI subprocess dies after exactly ~60 seconds during complex single-turn queries that require multiple sequential tool calls (e.g., "read a note AND build a knowledge graph from it"). Multi-turn conversations where each turn does one tool call work fine.

**Root cause found:** The SDK's `Query` class reads `CLAUDE_CODE_STREAM_CLOSE_TIMEOUT` (default 60,000ms = 60s). When SDK MCP servers are registered, `wait_for_result_and_end_input()` uses `anyio.move_on_after(60s)` to wait for the first result, then **silently closes stdin** — killing the bidirectional control protocol mid-flight while the CLI is still processing tool calls.

**Location:** `claude_agent_sdk/_internal/query.py` line ~77:
```python
self._stream_close_timeout = float(os.environ.get("CLAUDE_CODE_STREAM_CLOSE_TIMEOUT", "60000")) / 1000.0
```

**Why multi-turn works:** Each turn is an independent `query()` call. The 60s timer resets per turn. Individual tool calls complete well within 60s.

**Why single-turn multi-tool fails:** The agent reasons → calls tool A → waits for result → reasons → calls tool B. The total elapsed time exceeds 60s, stdin gets closed, and tool B's control response can't be written.

## Plan

### Step 1: Set `CLAUDE_CODE_STREAM_CLOSE_TIMEOUT` to 5 minutes

**File:** `docker-compose.yml`

Add the environment variable to the claude-agent service:
```yaml
environment:
  - CLAUDE_CODE_STREAM_CLOSE_TIMEOUT=300000  # 5 min (default 60s was killing multi-tool queries)
```

This is the primary fix. 300s (5 min) gives ample time for complex multi-tool workflows within a single turn.

### Step 2: Revert graph_building evals to single-turn format

**File:** `evals/claude_agent/datasets/graph_building.json`

The workaround of splitting graph-001 and graph-002 into multi-turn is no longer needed. Revert to the more natural single-turn format:
- graph-001: "Read Calendar/20251218.md and build a knowledge graph from the entities in it" (single turn)
- graph-002: Keep as multi-turn (read → build → query) since that tests session continuity

### Step 3: Document the finding as a gotcha

**File:** `CLAUDE.md`

Update gotcha #3 to document the actual root cause and fix:
```
3. **`CLAUDE_CODE_STREAM_CLOSE_TIMEOUT` defaults to 60s** — kills multi-tool queries.
   Set to 300000 (5 min) in docker-compose.yml. The SDK silently closes stdin after this
   timeout when SDK MCP servers are present, breaking bidirectional tool control.
```

### Step 4: Add timeout to startup auth check log

**File:** `src/knowledge_agents/claude_agent/server.py`

Log the configured stream close timeout at startup so it's visible in logs:
```python
logger.info("Stream close timeout: %ss", os.environ.get("CLAUDE_CODE_STREAM_CLOSE_TIMEOUT", "60000 (default)"))
```

## Critical Files

| File | Change |
|------|--------|
| `docker-compose.yml` | Add `CLAUDE_CODE_STREAM_CLOSE_TIMEOUT=300000` |
| `evals/claude_agent/datasets/graph_building.json` | Revert graph-001 to single-turn |
| `CLAUDE.md` | Update gotcha #3 with root cause |
| `src/knowledge_agents/claude_agent/server.py` | Log timeout at startup |

## Verification

1. Rebuild: `docker compose up -d --build claude-agent`
2. Reseed auth: `make claude-agent-auth-seed`
3. Test the exact failing query directly:
   ```bash
   curl -s -m 300 -X POST http://localhost:8004/api/v1/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Read Calendar/20251218.md and build a knowledge graph from the entities in it"}'
   ```
4. Run full eval: `conda run -n knowledge-agents python -m evals.claude_agent.runner`
5. Target: 10/10 passed with single-turn graph building working
6. Unit tests: `conda run -n knowledge-agents pytest tst/unit/claude_agent/ -v -m unit`
