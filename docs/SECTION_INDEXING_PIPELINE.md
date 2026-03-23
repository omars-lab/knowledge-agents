# Section Indexing Pipeline

> **Living Document** — update when changing the pipeline, models, or storage schema.

## Overview

The section indexing pipeline parses NotePlan files into heading-level sections, optionally summarizes each section via a local LLM, generates embeddings, and stores everything in Qdrant (for semantic search) and Neo4j (for graph queries).

**Why section-level?** Whole-file embeddings (the legacy `app_actions_collection`) lose granularity — a 500-line note with 10 sections gets one vector. Section-level indexing lets queries find the *specific section* that's relevant, not just the file.

## Pipeline Architecture

```
NotePlan Files (Calendar/*.md, Notes/**/*.md)
     │
     ▼
┌──────────────────────────────────────┐
│  Phase A: Discover + Parse           │
│  - Find files modified in last 30d   │
│  - Delta detect via SHA256 hashes    │
│  - Split into sections (H1/H2/H3)   │
│  - Build heading paths               │
│  Result: list[SectionData]           │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│  Phase B: Summarize (optional)       │
│  - Load ministral-3-14b on Mac Studio│
│  - Skip sections < 200 tokens        │
│  - Bounded concurrency (default 3)   │
│  Result: SectionData.summary filled  │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│  Phase C: Embed                      │
│  - Load qwen3-embedding-8b           │
│  - Embed: heading_path + summary +   │
│    raw_text (4096 dimensions)        │
│  - Batched (default 10 per batch)    │
│  Result: SectionData.embedding filled│
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│  Phase D: Store                      │
│  - Qdrant: upsert to                │
│    sections_collection               │
│  - Neo4j: create Section nodes       │
│    linked to Note via HAS_SECTION    │
│  - Neo4j: link Section → Entity      │
│    via CONTAINS                      │
│  - Update Note.content_hash          │
└──────────────────────────────────────┘
```

## Quick Start

```bash
# Index recent notes (delta — only changed files, no summarization)
make seed-sections

# Full re-index all notes
make seed-sections-full

# With LLM summarization (requires ministral-3-14b loaded on Mac Studio)
make seed-sections-summarize
```

## CLI Reference

```bash
python scripts/seed_sections.py [options]

Required:
  --noteplan-dir PATH     NotePlan root directory

Optional:
  --summarize             Enable LLM summarization (default: off)
  --summarize-model MODEL LLM model for summarization (default: lm_studio/ministral-3-14b-reasoning)
  --full-reindex          Re-index all files, ignore delta detection
  --concurrency N         Max parallel LLM calls (default: 3)
  --batch-size N          Sections per embedding batch (default: 10)
  --delay SECONDS         Delay between batches for rate limiting (default: 0.5)
```

### Example Output

```
📁 Discovering files...
  Found 216 files, 38 changed

📝 Phase A: Parsing sections...
  38 files → 187 sections

🧠 Phase B: Summarizing (ministral-3-14b)...
  142 summarized, 45 skipped (< 200 tokens)

🔢 Phase C: Embedding (text-embedding-qwen3-embedding-8b)...
  187 sections embedded

💾 Phase D: Storing...
  Qdrant: 187 points → sections_collection
  Neo4j: 187 Section nodes, 342 entity links

✅ Done in 6m 18s  |  187 sections  |  38 files  |  342 entity links
```

## What Gets Stored

### Qdrant (`sections_collection`)

Each section becomes a vector point:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | MD5 of `{file_path}::section_{index}` |
| `vector` | float[4096] | Qwen3-Embedding-8B vector |
| `file_path` | string | Relative path from NotePlan root |
| `section_index` | int | 0-based index within file |
| `heading` | string? | Section heading text |
| `heading_level` | int? | 1-3 for H1-H3 |
| `heading_path` | string | Hierarchical path: "H1 > H2 > H3" |
| `has_summary` | bool | Whether summary was generated |
| `token_count` | int | Estimated token count |
| `content_hash` | string | SHA256 of source file |

**Embedding text** (what gets embedded):
```
{heading_path}

Summary: {summary}

{raw_text}
```

If no summary: `{heading_path}\n\n{raw_text}`

### Neo4j (Section nodes)

```cypher
-- Section node
(:Section {
    section_id: "Calendar/20260323.md::section_0",
    file_path: "Calendar/20260323.md",
    section_index: 0,
    heading: "Moving Faster",
    heading_level: 1,
    heading_path: "Moving Faster",
    raw_text: "* Tokens / Claude Access...",
    summary: "Discussion of resources needed...",
    token_count: 450,
    content_hash: "abc123...",
    last_processed: "2026-03-23T..."
})

-- Relationships
(:Note {file_path: "Calendar/20260323.md"})-[:HAS_SECTION {section_index: 0}]->(:Section)
(:Section)-[:CONTAINS]->(:Entity {name: "Claude"})
```

## Delta Indexing

Files are tracked by **SHA256 content hash** stored on `Note.content_hash` in Neo4j.

On each run:
1. Compute SHA256 of each NotePlan file
2. Query Neo4j for stored hashes: `MATCH (n:Note) RETURN n.file_path, n.content_hash`
3. Compare — only re-index files where hash differs or is missing
4. After successful indexing, update `Note.content_hash`

To force re-index: use `--full-reindex` flag.

## Section Splitting

Uses `src/knowledge_agents/utils/text_splitters.py`:

- **Markdown files**: Split by H1/H2/H3 headings via LangChain's `MarkdownHeaderTextSplitter`
- **Non-markdown**: Single section (entire file)
- **Large sections** (> 8000 tokens): Auto-chunked at paragraph boundaries
- **Heading path**: Built from LangChain metadata (all ancestor headers)

Example — a file with:
```markdown
# Projects
## AI Agent
### Architecture
Content about architecture...
### Deployment
Content about deployment...
## Data Pipeline
Content about pipeline...
```

Produces 3 sections:
| Index | Heading | Heading Path | Level |
|-------|---------|-------------|-------|
| 0 | Architecture | Projects > AI Agent > Architecture | 3 |
| 1 | Deployment | Projects > AI Agent > Deployment | 3 |
| 2 | Data Pipeline | Projects > Data Pipeline | 2 |

## Summarization (Optional)

When `--summarize` is enabled:
- Sections ≥ 200 tokens are summarized via local LLM
- Sections < 200 tokens are skipped (already concise)
- Model: `ministral-3-14b-reasoning` on Mac Studio (via LiteLLM proxy)
- Bounded concurrency: `asyncio.Semaphore` (default 3 parallel calls)
- Prompt: `"Summarize this note section in 1-2 sentences. Context: {heading_path}"`

**Phased execution**: All summarization happens in Phase B with one model loaded. Then the model switches to the embedding model for Phase C. Only **2 model loads** total regardless of file count.

## LM Studio Model Requirements

| Phase | Model | Size | Purpose |
|-------|-------|------|---------|
| B (Summarize) | `Qwen3.5-35B-A3B` (MoE) | ~20 GB | Section summarization (3B active params, 85.3 MMLU-Pro) |
| C (Embed) | `text-embedding-qwen3-embedding-8b` | 4.68 GB | 4096-dim embeddings (MTEB #1) |

Check/load models:
```bash
make lm-studio-status              # Check what's loaded
make lm-studio-load-embeddings     # Load embedding model
```

## Collections

| Collection | Level | Dims | Use |
|-----------|-------|------|-----|
| `sections_collection` | Section | 4096 | Fine-grained retrieval (this pipeline) |
| `app_actions_collection` | Whole-file | 4096 | Legacy coarse search |

Both use Qwen3-Embedding-8B with COSINE distance.

## Key Files

| File | Purpose |
|------|---------|
| `scripts/seed_sections.py` | Pipeline orchestrator |
| `src/knowledge_agents/types/section.py` | SectionData, PipelineStats models |
| `src/knowledge_agents/services/summarizer.py` | Async batch summarization |
| `src/knowledge_agents/utils/text_splitters.py` | Section splitting with heading paths |
| `src/knowledge_agents/utils/delta_tracker.py` | Content hash delta detection |
| `src/knowledge_agents/utils/graph_utils.py` | `create_section_nodes()`, `link_section_entities()` |
| `docs/GRAPH_SCHEMA.md` | Section node schema (living doc) |
| `docs/TECH_DESIGN.md` | Architecture decisions (living doc) |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Cannot connect to host` | LiteLLM proxy can't reach LM Studio | `make lm-studio-status` to verify, then `docker compose up -d --force-recreate llm-proxy` |
| Embeddings hang/timeout | LM Studio not running or model not loaded | `make lm-studio-status && make lm-studio-load-embeddings` |
| `0 sections to process` | All files already indexed (delta) | `make seed-sections-full` to force re-index |
| Binary file warnings | Attachments (.jpg, etc.) in Notes | Normal — these are auto-skipped |
| Section count mismatch (Qdrant vs Neo4j) | Sections without embeddings not stored in Qdrant | Check `stats.errors` in pipeline output |
