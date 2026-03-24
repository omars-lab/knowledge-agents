# Temporal Knowledge Tools: Time-Based Queries, Changelog, and Version Tracking

## Context

Graphiti stores temporal data on every edge (`valid_at`, `invalid_at`, `expired_at`, `created_at`) and supports `SearchFilters` with `DateFilter` for time-based queries. However, none of this is exposed through our MCP tools. Additionally, our pipeline always stamps episodes with `datetime.now()`, losing historical timing from the actual notes.

**Three gaps to fill:**
1. **No temporal search** — `query_knowledge_graph` can't filter by date
2. **No changelog** — can't ask "what changed between two dates?"
3. **No historical timestamps** — all episodes stamped "now" instead of actual note dates

**Git integration:** NotePlan files are NOT in a git repo, so git commit hashes aren't available. Instead, we'll use **file modification timestamps** and **calendar note dates** (parseable from filename: `Calendar/20251218.md` → `2025-12-18`).

## Plan

### Step 1: Fix reference_time — use actual note dates, not now()

**Files:** `scripts/seed_sections.py`, `src/knowledge_agents/claude_agent/tools.py`

When ingesting episodes, derive `reference_time` from the note:
- **Calendar notes** (`Calendar/YYYYMMDD.md`): parse date from filename
- **Regular notes**: use file modification time from filesystem
- **Fallback**: `datetime.now()` only if no date available

```python
import re
from datetime import datetime, timezone

def _derive_reference_time(file_path: str, noteplan_dir: Path = None) -> datetime:
    """Derive the best reference time for a note."""
    # Calendar note: parse YYYYMMDD from filename
    match = re.match(r"Calendar/(\d{4})(\d{2})(\d{2})\.md$", file_path)
    if match:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), tzinfo=timezone.utc)
    # Regular note: use file modification time
    if noteplan_dir:
        full_path = noteplan_dir / file_path
        if full_path.exists():
            return datetime.fromtimestamp(full_path.stat().st_mtime, tz=timezone.utc)
    # Fallback
    return datetime.now(timezone.utc)
```

Update `seed_sections.py` Phase D and `build_knowledge_graph` tool to use this.

### Step 2: Add temporal search parameters to query_knowledge_graph

**File:** `src/knowledge_agents/claude_agent/tools.py`

Add `as_of_date` and `date_range` parameters to `query_knowledge_graph`:

```python
@tool(name="query_knowledge_graph", input_schema={
    "query": {"type": "string"},
    "as_of_date": {"type": "string", "description": "ISO date — only return facts valid as of this date (YYYY-MM-DD)"},
    "after_date": {"type": "string", "description": "Only return facts created after this date"},
    "before_date": {"type": "string", "description": "Only return facts created before this date"},
    "limit": {"type": "integer"},
})
```

Implementation uses Graphiti's `SearchFilters`:
```python
from graphiti_core.search.search_filters import SearchFilters, DateFilter, ComparisonOperator

search_filter = None
if args.get("as_of_date"):
    dt = datetime.fromisoformat(args["as_of_date"])
    search_filter = SearchFilters(
        created_at=[[DateFilter(date=dt, comparison_operator=ComparisonOperator.less_than_equal)]],
        expired_at=[[DateFilter(date=None, comparison_operator=ComparisonOperator.is_null)]]  # not yet expired
    )
```

### Step 3: Add knowledge changelog tool

**File:** `src/knowledge_agents/claude_agent/tools.py`

New MCP tool: `knowledge_changelog`

```python
@tool(name="knowledge_changelog", description="Show what changed in the knowledge graph between two dates")
async def knowledge_changelog(args):
    """Query edges created/expired between two dates."""
    start_date = parse(args["start_date"])
    end_date = parse(args["end_date"])

    # New facts (edges created in range)
    new_facts = cypher: MATCH ()-[r:RELATES_TO]->()
        WHERE r.created_at >= $start AND r.created_at <= $end
        RETURN r.name, r.fact, r.created_at

    # Expired facts (edges that became invalid in range)
    expired_facts = cypher: MATCH ()-[r:RELATES_TO]->()
        WHERE r.expired_at >= $start AND r.expired_at <= $end
        RETURN r.name, r.fact, r.expired_at

    # New entities (created in range)
    new_entities = cypher: MATCH (e:Entity)
        WHERE e.created_at >= $start AND e.created_at <= $end
        RETURN e.name, e.created_at

    # New episodes (ingested in range)
    new_episodes = cypher: MATCH (ep:Episodic)
        WHERE ep.created_at >= $start AND ep.created_at <= $end
        RETURN ep.name, ep.source_description, ep.created_at
```

### Step 4: Store content hash as episode metadata

**File:** `scripts/seed_sections.py`, `src/knowledge_agents/claude_agent/graphiti_client.py`

Since NotePlan isn't in git, store the **content hash** (SHA256) as episode metadata. This enables:
- "What knowledge came from this specific version of the file?"
- Change detection: if content_hash differs, facts may have changed

Pass content_hash via episode source_description or a custom field:
```python
await graphiti.add_episode(
    name=section.heading,
    episode_body=section.raw_text,
    source_description=f"NotePlan {file_path} :: hash={content_hash}",
    reference_time=derive_reference_time(file_path),
    group_id="noteplan",
)
```

### Step 5: Update prompts for temporal awareness

**File:** `src/knowledge_agents/claude_agent/prompts.py`

Add temporal workflow guidance:
```
### Temporal Queries
- Use `as_of_date` to ask "what did we know as of March 1?"
- Use `after_date`/`before_date` to filter to a time range
- Use `knowledge_changelog` to see what changed between dates
- Calendar notes automatically carry their date as reference_time
```

### Step 6: Update tests and docs

- Add unit tests for temporal search params and changelog tool
- Update `docs/GRAPH_SCHEMA.md` — document temporal fields on edges
- Update `docs/GRAPHITI_INTEGRATION.md` — add temporal use cases
- Update `CLAUDE.md` — add changelog to Key Commands if Makefile target added

## Critical Files

| File | Change |
|------|--------|
| `src/knowledge_agents/claude_agent/tools.py` | Add temporal params to query tool, add changelog tool |
| `scripts/seed_sections.py` | Use actual note dates for reference_time |
| `src/knowledge_agents/claude_agent/prompts.py` | Temporal workflow guidance |
| `src/knowledge_agents/claude_agent/graphiti_client.py` | Add _derive_reference_time helper |
| `tst/unit/claude_agent/test_tools.py` | Tests for temporal params + changelog |
| `docs/GRAPH_SCHEMA.md` | Document temporal edge fields |
| `docs/GRAPHITI_INTEGRATION.md` | Temporal use cases |

## Verification

1. Unit tests: `make claude-agent-test` — all pass
2. Re-index with historical dates: `make seed-sections-full` — episodes get correct reference_time
3. Temporal search: ask agent "What did I know about AI in January 2026?" — should filter by date
4. Changelog: ask agent "What changed in my knowledge graph this week?" — should show new/expired facts
5. Langfuse: traces show temporal search filter params

## Context

Graphiti spike failed (0/5) because Qwen3.5-9B can't produce structured JSON — it routes all output to `reasoning_content` with empty `content` (LM Studio bug specific to the 9B model with `response_format=json_schema`).

**Root cause confirmed:** NOT a token budget issue. The 35B-A3B model produces valid JSON correctly with fewer tokens (917 vs 2000+). The 9B model has a server-side routing bug.

**Solution:** Use **two models** — 35B-A3B for Graphiti extraction (needs structured output), 9B for summarization (needs concise text). Both are already loaded on Mac Studio.

**Goal:** Get Graphiti fully integrated end-to-end as the primary graph engine, replacing our hand-built `graph_utils.py` pipeline.

## Plan

### Step 1: Fix spike script — use 35B-A3B for extraction

**File:** `scripts/spike_graphiti.py`

Change `LLM_MODEL = "qwen3.5-9b"` → `"qwen3.5-35b-a3b"`. Keep custom `LMStudioClient` with `enable_thinking=False` and `max_tokens=8000` (35B needs headroom for reasoning + JSON output).

Re-run and verify episodes ingest successfully.

### Step 2: Create Graphiti integration module

**New file:** `src/knowledge_agents/claude_agent/graphiti_client.py`

Thin wrapper that initializes Graphiti with our LM Studio config:
```python
async def get_graphiti() -> Graphiti:
    """Initialize Graphiti with LM Studio (35B for extraction, local embeddings)."""
```

Key config:
- LLM: `qwen3.5-35b-a3b` via `LMStudioClient` (custom, disables thinking)
- Embedder: `text-embedding-qwen3-embedding-8b` via `OpenAIEmbedder`
- Reranker: `qwen3.5-35b-a3b` via custom client
- Neo4j: existing `bolt://localhost:7687` with `group_id="noteplan"`
- Graceful degradation: returns None if Graphiti init fails

### Step 3: Replace `build_knowledge_graph` tool with Graphiti

**File:** `src/knowledge_agents/claude_agent/tools.py`

Replace the current `build_knowledge_graph` tool implementation:

**Before:** Agent extracts entities manually → `create_graph_nodes_and_relationships()` → Neo4j MERGE
**After:** Pass note content to `graphiti.add_episode()` → Graphiti extracts entities automatically → temporal graph

```python
@tool(name="build_knowledge_graph", ...)
async def build_knowledge_graph(args):
    graphiti = await get_graphiti()
    await graphiti.add_episode(
        name=args["file_path"],
        episode_body=note_content,
        source_description=f"NotePlan {args['file_path']}",
        reference_time=datetime.now(timezone.utc),
        group_id="noteplan",
    )
```

The agent no longer needs to extract entities — Graphiti does it automatically. Simplify the tool's input schema to just `file_path` + optional `note_content`.

### Step 4: Replace `query_knowledge_graph` with Graphiti search

**File:** `src/knowledge_agents/claude_agent/tools.py`

Replace raw Cypher queries with Graphiti's hybrid search:

```python
@tool(name="query_knowledge_graph", ...)
async def query_knowledge_graph(args):
    graphiti = await get_graphiti()
    results = await graphiti.search(
        args["query"],
        group_ids=["noteplan"],
        num_results=args.get("limit", 10),
    )
    # Format results for the agent
```

Keep the existing Cypher tool as a fallback (`query_knowledge_graph_cypher`) for advanced queries.

### Step 5: Update section indexing pipeline to use Graphiti

**File:** `scripts/seed_sections.py`

In Phase D (Store), replace `create_section_nodes()` + `link_section_entities()` with Graphiti episodes:

```python
# Instead of creating Section nodes manually:
for section in file_sections:
    await graphiti.add_episode(
        name=section.heading or f"Section {section.section_index}",
        episode_body=section.raw_text,
        source_description=f"NotePlan {section.file_path} :: {section.heading_path}",
        reference_time=datetime.now(timezone.utc),
        group_id="noteplan",
    )
```

This gives us automatic entity extraction, temporal tracking, and hybrid search — all from the indexing pipeline.

### Step 6: Update SVG renderer to query Graphiti graph

**File:** `scripts/render_graph.py`

Update Neo4j queries to work with Graphiti's schema:
- Entities: `MATCH (e:Entity) WHERE e.group_id = 'noteplan'`
- Relationships: `MATCH (e1:Entity)-[r:RELATES_TO]->(e2:Entity) WHERE r.group_id = 'noteplan'`
- Episodes: `MATCH (ep:Episodic) WHERE ep.group_id = 'noteplan'`

The link resolver works as before — entity properties are stored in Graphiti's `attributes` dict.

### Step 7: Update model config

**File:** `docs/MODEL_DECISIONS.md`

Record the two-model strategy:
- **Summarization:** Qwen3.5-9B (eval score 0.71, best for concise text)
- **Extraction (Graphiti):** Qwen3.5-35B-A3B (reliable structured JSON output)
- **Embeddings:** Qwen3-Embedding-8B (MTEB #1, unchanged)

### Step 8: Clean up deprecated code

Remove (user confirmed no backward compat needed):
- `src/knowledge_agents/utils/graph_utils.py` — `create_graph_nodes_and_relationships()`, `create_section_nodes()`, `link_section_entities()` (replaced by Graphiti)
- `src/knowledge_agents/types/graph.py` — `Entity`, `Relationship`, `GraphBuilderAgentOutput` (replaced by Graphiti's internal types)
- Old graph builder agent in `src/knowledge_agents/agents/graph_builder_agent.py`
- Old graph builder prompt in `src/knowledge_agents/prompts/graph_builder_agent.py`

Keep:
- `setup_graph_schema()` — still needed for our Note/Section indexes
- `src/knowledge_agents/claude_agent/link_resolver.py` — still needed for SVG rendering
- `docs/GRAPH_SCHEMA.md` — update to document Graphiti's schema

### Step 9: Update GRAPH_SCHEMA.md for Graphiti

Replace hand-built schema with Graphiti's:
- Entity nodes: Graphiti `Entity` with `group_id`, `labels`, `summary`, `attributes`
- Episodes: Graphiti `Episodic` (replaces our Section nodes for provenance)
- Relationships: Graphiti `RELATES_TO` edges with temporal validity (`valid_at`, `invalid_at`, `expired_at`)
- Keep our Note nodes (file_path, xcallback_url) as metadata layer

### Step 10: Update living docs

- `docs/TECH_DESIGN.md` — Graphiti as primary graph engine
- `docs/SECTION_INDEXING_PIPELINE.md` — Phase D uses Graphiti episodes
- `docs/MODEL_DECISIONS.md` — two-model strategy
- `CLAUDE.md` — update gotchas (9B can't do structured output, use 35B for extraction)
- `docs/USE_CASES.md` — update UC-2 (graph building via Graphiti)

## Critical Files

| File | Action |
|------|--------|
| `scripts/spike_graphiti.py` | Fix: use 35B-A3B, re-run, verify |
| `src/knowledge_agents/claude_agent/graphiti_client.py` | New: Graphiti init with LM Studio |
| `src/knowledge_agents/claude_agent/tools.py` | Refactor: build_knowledge_graph → Graphiti episodes |
| `scripts/seed_sections.py` | Refactor: Phase D → Graphiti episodes |
| `scripts/render_graph.py` | Update: query Graphiti schema |
| `src/knowledge_agents/utils/graph_utils.py` | Remove deprecated functions |
| `docs/GRAPH_SCHEMA.md` | Rewrite for Graphiti schema |
| `docs/MODEL_DECISIONS.md` | Add two-model strategy |
| All living docs | Update references |

## Verification

1. Fix spike: `python scripts/spike_graphiti.py` → 5/5 sections succeed
2. Unit tests: `make claude-agent-test` → 44 tests pass
3. Agent chat: `make claude-agent-chat MSG="build a knowledge graph from Calendar/20251218.md"` → uses Graphiti
4. Section indexing: `make seed-sections` → episodes appear in Neo4j
5. Graph render: `make claude-agent-graph` → SVG shows Graphiti entities
6. Langfuse: traces show Graphiti extraction calls
7. Search: agent can query the graph via natural language (Graphiti hybrid search)
