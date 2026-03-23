# Note Indexing Pipeline: Section-Level Chunking, Summarization, and Embeddings

## Context

The current pipeline embeds **whole files** as single vectors in Qdrant (`app_actions_collection`). This means a 500-line note with 10 sections gets one embedding — queries can find the file but not the relevant section. Calendar notes with one task get the same treatment as dense project notes.

The codebase **already has** section-level splitting (`text_splitters.py`) and per-section embedding generation (`data_persistence.py`) — but these are never stored in Qdrant or Neo4j. The infrastructure is 80% built.

**Goal:** Build a pipeline that parses notes into sections, optionally summarizes via local LLM, generates per-section embeddings, and stores Section nodes in Neo4j + section vectors in Qdrant. Support delta indexing via content hashes.

## Key Design Decisions

1. **Summarization model:** `ministral-3-14b-reasoning` — fast enough for batch processing, adequate quality for personal notes. Skip sections under 200 tokens (they're already concise).

2. **What to embed:** `"{heading_path}\n\nSummary: {summary}\n\n{raw_text}"` — three signal layers: position context, noise-reduced summary, and full detail. If no summary, just `"{heading_path}\n\n{raw_text}"`.

3. **Section granularity:** H1/H2/H3 (existing `split_content_into_sections()` behavior). Headingless calendar notes → single section. Already handled.

4. **Embeddings in Qdrant only, not Neo4j** — 4096-dim vectors in Neo4j properties would bloat nodes and slow Cypher. Pattern: Qdrant finds sections by similarity → Neo4j enriches with graph context.

5. **New `sections_collection`** — keeps backward compat with `app_actions_collection`. Different metadata schemas, independent lifecycle.

6. **LM Studio model switching:** Summarize ALL sections first (ministral-3-14b), THEN embed ALL (qwen3-embedding-8b). LM Studio serves one model at a time — phased execution avoids model swapping per file.

## Architecture

```
NotePlan Files
     │
     ▼
[1. Discover + Delta Detect]
     │  traversal.py + content hash comparison
     ▼
[2. Parse + Split into Sections]
     │  parser.py + text_splitters.py (existing, extend with heading_path)
     ▼
[3. Summarize (optional, batched)]
     │  LiteLLM → ministral-3-14b on Mac Studio
     │  Skip sections < 200 tokens
     ▼
[4. Generate Embeddings (batched)]
     │  LiteLLM → qwen3-embedding-8b on Mac Studio
     ▼
[5. Store in Qdrant]           [6. Store in Neo4j]
     sections_collection            Section nodes
     (4096-dim, COSINE)             Note ─HAS_SECTION─▶ Section
                                    Section ─CONTAINS─▶ Entity
```

## Plan

### Step 1: Add `Section` type and schema

**New file:** `src/knowledge_agents/types/section.py`

```python
class SectionData(BaseModel):
    file_path: str
    section_index: int
    heading: str | None
    heading_level: int | None
    heading_path: str           # "Projects > AI Agent > Architecture"
    raw_text: str
    summary: str | None = None
    embedding: list[float] | None = None
    token_count: int
    content_hash: str | None = None  # SHA256 of source file content
```

**Update:** `docs/GRAPH_SCHEMA.md` — add Section node type:
- Properties: `section_id` (UNIQUE, `{file_path}::section_{index}`), `file_path`, `section_index`, `heading`, `heading_level`, `heading_path`, `raw_text`, `summary`, `token_count`, `content_hash`, `last_processed`
- New relationship: `HAS_SECTION` (Note → Section, with `section_index` property)
- Extend `CONTAINS` to be valid from Section → Entity

### Step 2: Extend `text_splitters.py` with heading paths

**Modify:** `src/knowledge_agents/utils/text_splitters.py`

Add `include_heading_path=True` parameter to `split_content_into_sections()`. The LangChain `MarkdownHeaderTextSplitter` already stores all ancestor headers in `split.metadata` (`{"Header 1": "Projects", "Header 2": "AI Agent"}`). Build the path:
```python
path_parts = [split.metadata[f"Header {i}"] for i in range(1, 4) if f"Header {i}" in split.metadata]
heading_path = " > ".join(path_parts)
```

Return `heading_path` in each section dict alongside existing `content`, `heading`, `heading_level`, `section_index`.

### Step 3: Create delta tracker

**New file:** `src/knowledge_agents/utils/delta_tracker.py`

Uses SHA256 content hashes (reuse existing `compute_content_hash()` from `cache_utils.py`):
```python
def get_indexed_hashes(driver, database) -> dict[str, str]:
    """Query Neo4j: MATCH (n:Note) RETURN n.file_path, n.content_hash"""

def compute_delta(files, noteplan_dir, indexed_hashes) -> (to_index, to_remove):
    """Compare current file hashes against indexed. Returns files needing re-index."""
```

### Step 4: Create summarizer service

**New file:** `src/knowledge_agents/services/summarizer.py`

Async batch summarization via LiteLLM proxy → ministral-3-14b:
```python
async def summarize_sections_batch(
    sections: list[SectionData],
    model: str = "lm_studio/ministral-3-14b-reasoning",
    concurrency: int = 3,
    min_tokens: int = 200,
) -> list[SectionData]:
```

- Uses `asyncio.Semaphore(concurrency)` for bounded parallel LLM calls (default 3)
- Skips sections under 200 tokens (summary = None)
- Configurable `delay_between_batches` for rate limiting (default 1s)
- Prompt: `"Summarize this note section in 1-2 sentences. Context: {heading_path}\n\n{text}"`
- Calls LiteLLM proxy at `localhost:4000` with API key `sk-1234`
- Reports progress via `rich.progress` bar (total sections, completed, skipped, time elapsed)

### Step 5: Update Neo4j schema + graph_utils

**Modify:** `src/knowledge_agents/utils/graph_utils.py`

Add to `setup_graph_schema()`:
```python
"CREATE CONSTRAINT section_id IF NOT EXISTS FOR (s:Section) REQUIRE s.section_id IS UNIQUE"
"CREATE INDEX section_file_path IF NOT EXISTS FOR (s:Section) ON (s.file_path)"
```

Add new functions:
```python
def create_section_nodes(driver, file_path, sections: list[SectionData], database) -> int:
    """Delete existing sections for file, create new ones, link to Note via HAS_SECTION."""

def link_section_entities(driver, section_id, entity_names: list[str], database) -> int:
    """Create Section -[:CONTAINS]-> Entity relationships."""
```

`create_section_nodes` is idempotent: `DETACH DELETE` old sections for the file, then create fresh ones.

### Step 6: Config changes

**Modify:** `src/knowledge_agents/config/api_config.py` — add `qdrant_sections_collection_name = "sections_collection"`

**Modify:** `src/knowledge_agents/claude_agent/config.py` — add `qdrant_sections_collection_name: str = "sections_collection"`

### Step 7: Pipeline script

**New file:** `scripts/seed_sections.py`

Main orchestrator — async with rich CLI UX:
```python
async def seed_sections(
    noteplan_dir: Path,
    settings: Settings,
    full_reindex: bool = False,
    summarize: bool = True,
    concurrency: int = 3,          # max parallel LLM calls
    embedding_batch_size: int = 10, # sections per embedding batch
    delay_between_batches: float = 1.0,  # seconds between batches (rate limiting)
):
```

**CLI with `rich` progress bars:**
```bash
python scripts/seed_sections.py --noteplan-dir /noteplan --summarize --concurrency 3

📁 Discovering files...
  Found 42 files, 38 changed (delta detection)

📝 Phase A: Parsing sections...
  ━━━━━━━━━━━━━━━━━━━━━━━━━ 38/38 files  187 sections

🧠 Phase B: Summarizing (ministral-3-14b)...
  ━━━━━━━━━━━━━━━━━━━━━━━━━ 142/142 sections  (45 skipped < 200 tokens)
  ⏱ 4m 23s  💰 Free (local LLM)

🔢 Phase C: Embedding (qwen3-embedding-8b)...
  ━━━━━━━━━━━━━━━━━━━━━━━━━ 187/187 sections  19 batches
  ⏱ 1m 12s  💰 Free (local LLM)

💾 Phase D: Storing...
  Qdrant: 187 points upserted to sections_collection
  Neo4j: 187 Section nodes, 342 entity links
  ━━━━━━━━━━━━━━━━━━━━━━━━━ 38/38 files

✅ Done in 6m 18s  |  187 sections  |  38 files  |  342 entity links
```

Uses `rich` library for progress bars (already a common Python dep). Falls back to plain logging if `rich` not installed.

The pipeline runs in **staged phases across ALL files** to avoid model switching:

```
Phase A: Parse all files
  For each changed file:
    1. Read content
    2. Split into sections with heading paths
    3. Build SectionData objects
    4. Save to in-memory list
  Result: all_sections: list[SectionData]

Phase B: Summarize all sections (one model load)
  1. Load ministral-3-14b on Mac Studio
  2. Summarize all sections in batches (skip < 200 tokens)
  3. Update SectionData.summary in place
  Result: all_sections now have summaries

Phase C: Embed all sections (one model load)
  1. Load qwen3-embedding-8b on Mac Studio
  2. Build embedding text: "{heading_path}\n\nSummary: {summary}\n\n{raw_text}"
  3. Generate embeddings in batches
  4. Update SectionData.embedding in place
  Result: all_sections now have embeddings

Phase D: Store everything (no LLM needed)
  For each file's sections:
    1. Upsert to Qdrant sections_collection
    2. Create Section nodes in Neo4j
    3. Link sections to entities (substring match)
    4. Update Note.content_hash
```

This means only **2 model loads** total regardless of file count, not 2 per file. The `lm_studio_ctl.sh` script handles the switch:
```bash
./scripts/lm_studio_ctl.sh load-model --remote mac-studio "ministral-3-14b"
# Phase B runs...
./scripts/lm_studio_ctl.sh load-model --remote mac-studio "qwen3-embedding-8b"
# Phase C runs...
```

Qdrant payload per point:
```json
{
    "file_path": "Notes/project.md",
    "section_index": 2,
    "heading": "Architecture",
    "heading_level": 3,
    "heading_path": "Projects > AI Agent > Architecture",
    "has_summary": true,
    "token_count": 450,
    "modified_at": "2026-03-20T10:30:00"
}
```

### Step 8: Add `section_search` tool to Claude Agent

**Modify:** `src/knowledge_agents/claude_agent/tools.py`

Add new MCP tool:
```python
@tool(name="section_search", ...)
async def section_search(args: dict) -> dict:
    """Search note sections by semantic similarity.
    Returns section text, heading path, parent file, and similarity score."""
```

Queries `sections_collection` in Qdrant, returns section text + heading path + parent file. Add to `ALL_TOOLS` and `TOOL_NAMES`.

Update `prompts.py` to document the new tool.

### Step 9: Makefile targets

```makefile
seed-sections:        ## Index NotePlan sections (delta — only changed files)
seed-sections-full:   ## Full re-index all sections
seed-sections-status: ## Show indexing stats (files indexed, sections, last run)
```

### Step 10: Create `docs/TECH_DESIGN.md` — living architecture doc

**New file:** `docs/TECH_DESIGN.md`

A living document for architecture decisions, model choices, and infrastructure design. Contents:

- **Hardware:** Mac Studio M3 Ultra, 96GB — what it can run
- **Model decisions:** Why Qwen3-Embedding-8B for embeddings, why ministral-3-14b/Qwen3-30B-MoE for summarization
- **Pipeline architecture:** Section indexing flow diagram
- **Collection strategy:** `app_actions_collection` (whole-file, backward compat) vs `sections_collection` (section-level)
- **Embedding strategy:** Heading path + summary + raw text concatenation
- **Delta indexing:** Content hash comparison for incremental re-indexing
- **Claude Agent SDK learnings:** Transport timeout, rate limiting, model switching
- **Trade-offs considered:** Neo4j vectors vs Qdrant-only, summarization cost vs quality, section granularity

Add to CLAUDE.md Living Documents list.

### Step 11: Tests and docs

- `tst/unit/utils/test_text_splitters_heading_path.py` — heading path generation
- `tst/unit/utils/test_delta_tracker.py` — delta detection
- `tst/unit/services/test_summarizer.py` — mocked LLM summarization
- Update `docs/GRAPH_SCHEMA.md` — Section node, HAS_SECTION relationship
- Update `.claude/skills/knowledge-index.md` — reference seed-sections script

## Critical Files

| File | Action | Key Reuse |
|------|--------|-----------|
| `src/knowledge_agents/types/section.py` | Create | — |
| `src/knowledge_agents/services/summarizer.py` | Create | LiteLLM proxy pattern from tools.py |
| `src/knowledge_agents/utils/delta_tracker.py` | Create | `cache_utils.compute_content_hash()` |
| `scripts/seed_sections.py` | Create | Pattern from `seed_vector_store.py` |
| `src/knowledge_agents/utils/text_splitters.py` | Modify | Extend existing `split_content_into_sections()` |
| `src/knowledge_agents/utils/graph_utils.py` | Modify | Extend `setup_graph_schema()`, add Section functions |
| `src/knowledge_agents/claude_agent/tools.py` | Modify | Add `section_search` tool |
| `src/knowledge_agents/claude_agent/prompts.py` | Modify | Document `section_search` |
| `src/knowledge_agents/claude_agent/config.py` | Modify | Add `qdrant_sections_collection_name` |
| `docs/GRAPH_SCHEMA.md` | Modify | Add Section node type |
| `docs/TECH_DESIGN.md` | Create | Living arch doc: models, pipeline, trade-offs |
| `CLAUDE.md` | Modify | Add TECH_DESIGN.md to Living Documents |
| `Makefile` | Modify | Add seed-sections targets |

## LM Studio Model Switching Consideration

LM Studio serves one model at a time. The pipeline must be **phased**:
1. Load `ministral-3-14b-reasoning` → summarize all sections across all files
2. Load `qwen3-embedding-8b` → embed all sections
3. Store everything in Qdrant + Neo4j

The `lm_studio_ctl.sh` script can switch models:
```bash
./scripts/lm_studio_ctl.sh load-model --remote mac-studio "mistralai/ministral-3-14b-reasoning"
# ... summarize ...
./scripts/lm_studio_ctl.sh load-model --remote mac-studio "Qwen/Qwen3-Embedding-8B-GGUF/..."
# ... embed ...
```

## Hardware & Model Selection

**Mac Studio specs:** Apple M3 Ultra, 96GB unified memory. Can run models up to ~60GB.

**Current models installed:**

| Model | Size | Type | Installed |
|-------|------|------|-----------|
| `text-embedding-qwen3-embedding-8b` | 4.68 GB | Embedding | Yes |
| `text-embedding-nomic-embed-text-v1.5` | 84 MB | Embedding | Yes |
| `ministral-3-14b-reasoning` | 9.12 GB | Chat | Yes |
| `openai/gpt-oss-20b` | 12.10 GB | Chat | Yes |
| `qwen/qwen3-coder-30b` | 17.19 GB | Chat | Yes |
| `mistralai/devstral-small-2-2512` | 14.12 GB | Chat | Yes |

**Models worth installing (from LM Studio catalog search):**

| Model | Size (est.) | Why |
|-------|-------------|-----|
| `Qwen3 8B` | ~5 GB | Latest gen, excellent summarization, fast |
| `Qwen3 30B A3B (MoE)` | ~17 GB | MoE architecture: only 3B params active at inference, very fast, high quality |
| `jina-embeddings-v5-text-small-retrieval` | ~0.5 GB | State-of-art retrieval embeddings, smaller and possibly better than Qwen3-8B for search |

**Recommendation for this pipeline:**
- **Summarization:** `Qwen3 30B A3B (MoE)` if installed, otherwise `ministral-3-14b-reasoning`. The MoE model gives better quality at comparable speed since only 3B params are active.
- **Embedding:** `text-embedding-qwen3-embedding-8b` (4096 dims, matches existing Qdrant collection). Switching to Jina v5 would require re-indexing everything.

**Model decisions will be documented in `docs/TECH_DESIGN.md`** — a new living doc for architecture and model choices.

**Future:** `/model-select` skill (task #1) that inspects hardware, searches LM Studio catalog, and recommends models per task type.

## Cost & Performance Estimates

| Step | Time per file | Cost |
|------|--------------|------|
| Parse + split | <100ms | Free |
| Summarize (~5 sections × 200 tokens) | ~5-10s | Free (local LLM) |
| Embed (~5 sections × 4096 dims) | ~2-5s | Free (local LLM) |
| Neo4j store | ~200ms | Free |
| Qdrant upsert | ~50ms | Free |
| **Total per file** | **~10-20s** | **Free** |
| **100 files** | **~20-30 min** | **Free** |

## Verification

1. `make lm-studio-status` — verify Mac Studio is up, embedding model loaded
2. `make seed-sections` — run pipeline on recent files
3. `curl localhost:6333/collections/sections_collection` — verify collection exists with points
4. Test section search via agent: `/knowledge search sections about "machine learning"`
5. `make claude-agent-graph` — verify Section nodes appear in SVG
6. Unit tests: `make claude-agent-test`
