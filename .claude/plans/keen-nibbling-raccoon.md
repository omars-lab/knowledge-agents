# Graphiti Integration: End-to-End with Qwen3.5-35B-A3B for Extraction

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
