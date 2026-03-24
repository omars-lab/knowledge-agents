# Langfuse Migration: LLM Observability + Stack Simplification

## Context

We have a custom eval framework (runner + scorer + JSON results), hand-built session workspaces (JSON files per turn), 6 Prometheus LLM counters, and LLM-grading via Haiku. This works but is fragile, file-based, and lacks visualization for multi-turn traces.

**Current OTel/metrics state (broken):**
- Claude Agent `/metrics` — defined in code but not serving after latest rebuild
- Agentic API `/metrics` — only emitting Kong gateway metrics, not app-level LLM metrics
- **No OTel traces anywhere** — no spans, no trace context propagation
- No tracing of LLM calls (input/output/tokens/cost per call)

Langfuse (self-hosted) replaces most of this with a proper LLM observability platform: trace visualization, prompt versioning, eval scoring, cost tracking — all with a web UI. By migrating, we can **remove** session workspace files, LLM-specific Prometheus metrics, and custom eval grading, while **keeping** Loki (logs) and Prometheus (infra health only).

## What Changes

| Component | Before | After | Action |
|-----------|--------|-------|--------|
| Session workspaces (`build/sessions/`) | JSON files per turn | Langfuse traces | **Remove** `_write_session_metadata`, `_write_turn_artifacts` |
| LLM Prometheus metrics (6 counters) | `claude_agent_*` in server.py | Langfuse dashboard | **Remove** from server.py |
| Eval LLM grading (Haiku) | Custom scorer.py | Langfuse eval datasets + scoring | **Migrate** |
| Eval results JSON | `evals/results/*.json` | Langfuse eval runs | **Migrate** runner to post results to Langfuse |
| Grafana LLM dashboards | Custom panels | Langfuse UI | **Simplify** Grafana to infra-only |
| Loki (logs) | Container log aggregation | Same | **Keep** |
| Prometheus (infra) | Container health, uptime | Same (remove LLM counters) | **Keep** (simplified) |

## Plan

### Step 1: Add Langfuse to Docker Compose

Add 2 services (Langfuse v3 uses single container + existing Postgres):

```yaml
langfuse:
  image: langfuse/langfuse:latest
  ports:
    - "3210:3000"
  environment:
    - DATABASE_URL=postgresql://knowledge:knowledge123@postgres:5432/langfuse
    - NEXTAUTH_SECRET=langfuse-secret-change-me
    - NEXTAUTH_URL=http://localhost:3210
    - SALT=langfuse-salt-change-me
    - LANGFUSE_INIT_ORG_ID=knowledge-agents
    - LANGFUSE_INIT_ORG_NAME=Knowledge Agents
    - LANGFUSE_INIT_PROJECT_ID=knowledge-agents
    - LANGFUSE_INIT_PROJECT_NAME=Knowledge Agents
    - LANGFUSE_INIT_PROJECT_PUBLIC_KEY=pk-lf-knowledge
    - LANGFUSE_INIT_PROJECT_SECRET_KEY=sk-lf-knowledge
    - LANGFUSE_INIT_USER_EMAIL=admin@local
    - LANGFUSE_INIT_USER_PASSWORD=knowledge123
  depends_on:
    postgres:
      condition: service_healthy
  healthcheck:
    test: ["CMD-SHELL", "curl -sf http://localhost:3000/api/public/health || exit 1"]
    interval: 15s
    timeout: 10s
    retries: 5
    start_period: 30s
  restart: unless-stopped
```

Create `langfuse` database in Postgres init script or startup.

### Step 2: Create Langfuse tracing utility

**New file:** `src/knowledge_agents/utils/langfuse_trace.py`

Thin wrapper around the Langfuse Python SDK:
```python
from langfuse import Langfuse

_client: Langfuse | None = None

def get_langfuse() -> Langfuse | None:
    """Lazy-init Langfuse client. Returns None if not configured (graceful degradation)."""

def trace_llm_call(name, input, output, model, usage, metadata, parent_trace_id=None):
    """Record an LLM call as a Langfuse generation span."""

def trace_tool_call(name, input, output, parent_trace_id):
    """Record a tool invocation as a Langfuse span."""
```

Key design: **graceful degradation** — if Langfuse is down or not configured, all trace functions are no-ops. App continues working.

Config via env vars:
```
LANGFUSE_PUBLIC_KEY=pk-lf-knowledge
LANGFUSE_SECRET_KEY=sk-lf-knowledge
LANGFUSE_HOST=http://langfuse:3000
```

### Step 3: Instrument Claude Agent (Priority 1)

**File:** `src/knowledge_agents/claude_agent/agent.py`

In `stream_agent_response()`:
- Create a Langfuse trace at start (`trace = langfuse.trace(name="chat", input=message, session_id=session_id)`)
- Log each tool call as a span (`trace.span(name=tool_name, input=tool_input)`)
- On ResultMessage: update trace with output, cost, duration
- On error: update trace with error status

**Remove:** `_write_session_metadata()`, `_write_turn_artifacts()`, `_ensure_session_workspace()` — Langfuse replaces all of these.

**File:** `src/knowledge_agents/claude_agent/server.py`

Remove LLM-specific Prometheus metrics:
- Remove `CHAT_REQUESTS`, `CHAT_DURATION`, `TOOL_CALLS`, `RATE_LIMIT_EVENTS`, `COST_TOTAL`, `STREAM_REQUESTS`
- Keep `/health` and `/metrics` endpoints (Prometheus still serves infra health)
- Keep request-level logging (Loki)

### Step 4: Instrument Summarizer (Priority 2)

**File:** `src/knowledge_agents/services/summarizer.py`

In `summarize_sections_batch()`:
- Create parent trace: `trace = langfuse.trace(name="summarize_batch", metadata={"section_count": len(sections)})`
- Each `summarize_section()` call: `trace.generation(name="summarize_section", input=text, output=summary, model=model, usage={...})`

### Step 5: Instrument Embedding + Seed Pipeline (Priority 3)

**File:** `scripts/seed_sections.py`

In `phase_embed()`:
- Trace each embedding batch as a Langfuse generation
- Track model, batch size, token count

In `phase_summarize()`:
- Already instrumented via summarizer (Step 4)

### Step 6: Migrate Eval Framework to Langfuse

**File:** `evals/claude_agent/runner.py`

Instead of saving JSON results to `evals/results/`:
- Create a Langfuse dataset for each eval dataset (note_search, graph_building, etc.)
- Each test case becomes a dataset item
- Runner posts results as Langfuse scores on traces
- `--llm-grading` uses Langfuse's built-in annotation scoring

**File:** `evals/claude_agent/scorer.py`

- Remove `_llm_grade_quality()` and `_llm_grade_context_retention()` — use Langfuse eval functions instead
- Keep code-based scoring (tool_selection, output_contains) — post as Langfuse scores

### Step 7: Simplify Grafana

Remove LLM-specific dashboard panels. Keep:
- Container health (Docker stats)
- Neo4j/Qdrant/Postgres connection status
- Log volume (Loki)

LLM dashboards move to Langfuse UI at `http://localhost:3210`.

### Step 8: Update docs

- `docs/OBSERVABILITY.md` — add Langfuse section, update architecture diagram
- `CLAUDE.md` — add Langfuse to Living Documents, update Key Commands
- `docs/TECH_DESIGN.md` — update observability section
- `README.md` — add Langfuse to tech stack

### Step 9: Makefile targets

```makefile
langfuse-up:     ## Start Langfuse (requires: make docker-up for Postgres)
langfuse-open:   ## Open Langfuse UI in browser
langfuse-down:   ## Stop Langfuse
```

## Critical Files

| File | Action |
|------|--------|
| `docker-compose.yml` | Add langfuse service, create langfuse DB |
| `src/knowledge_agents/utils/langfuse_trace.py` | New: tracing utility |
| `src/knowledge_agents/claude_agent/agent.py` | Add traces, remove session workspace writes |
| `src/knowledge_agents/claude_agent/server.py` | Remove LLM Prometheus counters |
| `src/knowledge_agents/services/summarizer.py` | Add trace generation spans |
| `scripts/seed_sections.py` | Add batch tracing |
| `evals/claude_agent/runner.py` | Post results to Langfuse |
| `evals/claude_agent/scorer.py` | Remove LLM grading, post scores to Langfuse |
| `requirements-claude-agent.txt` | Add `langfuse` package |
| `docs/OBSERVABILITY.md` | Update architecture |
| `Makefile` | Add langfuse targets |

## Verification

1. `make langfuse-up` — Langfuse UI at http://localhost:3210
2. `make claude-agent-chat MSG="hello"` — trace appears in Langfuse
3. `make seed-sections-summarize` — batch traces appear with per-section generations
4. `make claude-agent-eval` — eval results appear as Langfuse dataset scores
5. Grafana still works for infra dashboards (no LLM panels)
6. App works with Langfuse down (graceful degradation)
