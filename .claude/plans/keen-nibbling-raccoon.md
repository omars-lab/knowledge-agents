# Fix 3 Failing Eval Cases (graph-001, graph-002, multi-002)

## Context

The eval framework runs 10 test cases. 7 pass, 3 fail with `CLIConnectionError: ProcessTransport is not ready for writing`. All 3 failing cases involve the `build_knowledge_graph` tool or multi-turn graph workflows. The CLI subprocess exits prematurely (~60s) during complex multi-tool operations.

**Root causes identified:**
1. **Blocking Neo4j I/O on the async event loop** — `build_knowledge_graph` calls synchronous Neo4j driver operations inside an async tool handler, blocking the event loop and preventing the SDK from servicing the CLI subprocess keepalive/control messages
2. **Neo4j schema setup on first call** — `_ensure_neo4j_schema()` runs 6 DDL statements synchronously on first graph write, compounding the blocking issue
3. **Agent uses system tools** — the `allowed_tools` setting may only control permissions, not tool visibility. The agent uses Claude Code system tools (Bash, Read, ToolSearch) instead of MCP tools, consuming turns and causing unpredictable behavior
4. **No error recovery** — when the transport dies, the 500 propagates with no useful info to the eval runner

## Plan

### Step 1: Move Neo4j schema setup to startup (init_tool_clients)

**File:** `src/knowledge_agents/claude_agent/tools.py`

Move `_ensure_neo4j_schema()` from the first `build_knowledge_graph` call to `init_tool_clients()`. This eliminates the schema DDL latency from tool execution and front-loads it to container startup where blocking is acceptable.

Remove `_ensure_neo4j_schema()` call from inside `build_knowledge_graph`.

### Step 2: Run Neo4j operations in a thread pool (unblock event loop)

**File:** `src/knowledge_agents/claude_agent/tools.py`

Wrap the synchronous `create_graph_nodes_and_relationships()` call in `asyncio.to_thread()` so it doesn't block the event loop. Same for `query_knowledge_graph`'s `session.run()`.

### Step 3: Restrict agent to MCP tools only via `tools` parameter

**File:** `src/knowledge_agents/claude_agent/agent.py`

Use `tools=TOOL_NAMES` in addition to `allowed_tools=TOOL_NAMES` to restrict the agent to ONLY our MCP tools. This prevents the agent from using Bash, Read, ToolSearch, etc., which consume turns and cause unpredictable behavior.

### Step 4: Increase max_turns for graph workflows

**File:** `src/knowledge_agents/claude_agent/config.py`

Graph building needs: reason → read_note → reason about entities → build_knowledge_graph → reason. That's 5+ turns minimum. Multi-turn graph workflows can need 15+.

Change default from 25 to 50.

### Step 5: Catch CLIConnectionError as 503 in server

**File:** `src/knowledge_agents/claude_agent/server.py`

Return a structured error with duration and hint instead of raw 500.

### Step 6: Update unit tests

**Files:** `tst/unit/claude_agent/test_tools.py`, `tst/unit/claude_agent/test_agent.py`

- Assert `tools=TOOL_NAMES` is set in options
- Account for `asyncio.to_thread` wrapping in tool tests
- Test schema initialization at startup

## Critical Files

| File | Change |
|------|--------|
| `src/knowledge_agents/claude_agent/tools.py` | Move schema to startup, async Neo4j ops |
| `src/knowledge_agents/claude_agent/agent.py` | Add `tools=TOOL_NAMES` to options |
| `src/knowledge_agents/claude_agent/config.py` | max_turns 25→50 |
| `src/knowledge_agents/claude_agent/server.py` | Catch CLIConnectionError as 503 |
| `tst/unit/claude_agent/test_tools.py` | Update for async wrapping |
| `tst/unit/claude_agent/test_agent.py` | Update for tools option |

## Verification

1. `conda run -n knowledge-agents pytest tst/unit/claude_agent/ -v -m unit` — all tests pass
2. Rebuild container: `docker compose up -d --build claude-agent`
3. Reseed auth: `make claude-agent-auth-seed`
4. Run full eval: `conda run -n knowledge-agents python -m evals.claude_agent.runner`
5. Target: 10/10 passed, 0 errors
