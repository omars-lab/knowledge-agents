# Technical Design Document

> **Living Document** — update when making architecture decisions, changing models, or modifying infrastructure.

## Hardware

**Mac Studio (remote LLM host)**
- Chip: Apple M3 Ultra
- Memory: 96GB unified
- Max comfortable model size: ~60GB
- SSH: `mac-studio` (configured in `~/.ssh/config`)
- LM Studio API: `mac-studio.local:1234`

## Model Decisions

### Embedding: Qwen3-Embedding-8B

| Property | Value |
|----------|-------|
| Model | `text-embedding-qwen3-embedding-8b` |
| Size | 4.68 GB |
| Dimensions | 4096 |
| Quantization | Q4_K_M |
| Collection | `sections_collection` (section-level), `app_actions_collection` (whole-file legacy) |

**Why:** Best balance of quality and speed for local inference. 4096 dimensions provide rich semantic representation. Already installed and tested.

**Alternatives considered:**
- `nomic-embed-text-v1.5` (768 dims, 84MB) — too low dimensionality for fine-grained section search
- `jina-embeddings-v5-text-small-retrieval` — state-of-art for retrieval but would require re-indexing everything; dimension mismatch with existing collection

### Summarization: Ministral-3-14B-Reasoning

| Property | Value |
|----------|-------|
| Model | `ministral-3-14b-reasoning` |
| Size | 9.12 GB |
| Use case | Batch note summarization |
| Concurrency | 3 parallel requests |

**Why:** Fast enough for batch processing hundreds of sections. 14B parameters produce adequate summaries for personal notes. Reasoning variant helps with structured extraction.

**Alternatives considered:**
- `Qwen3 30B A3B (MoE)` — only 3B active params at inference, potentially faster with better quality. Worth installing and benchmarking.
- `openai/gpt-oss-20b` — slower, no meaningful quality gain for this task
- Fine-tuned summarizers — over-specialized, lower general quality

### Claude Agent: Claude API (Opus/Sonnet via subscription)

The interactive agent uses Claude API via the Claude Agent SDK, not local models. Rate limited by subscription tier (`max` plan, `5x` rate limit).

## Section Indexing Pipeline

### Architecture

```
NotePlan Files → Parse → Split (H1/H2/H3) → Summarize → Embed → Store
                   │                              │           │        │
                   ▼                              ▼           ▼        ▼
              text_splitters.py           ministral-3-14b  qwen3-8b  Qdrant + Neo4j
```

### What Gets Embedded

Each section is embedded as a concatenation of three signal layers:
```
{heading_path}

Summary: {summary}

{raw_text}
```

- **Heading path** (e.g., "Projects > AI Agent > Architecture") provides hierarchical position context
- **Summary** provides noise-reduced semantic signal (optional, skip for sections < 200 tokens)
- **Raw text** preserves detail for long-tail retrieval

### Phased Execution

LM Studio serves one model at a time. The pipeline runs in phases:
1. **Phase A: Parse** — all files split into sections (no LLM needed)
2. **Phase B: Summarize** — load ministral-3-14b, summarize all sections
3. **Phase C: Embed** — load qwen3-embedding-8b, embed all sections
4. **Phase D: Store** — write to Qdrant + Neo4j (no LLM needed)

Only 2 model loads total regardless of file count.

### Delta Indexing

Files are tracked by SHA256 content hash stored on `Note.content_hash` in Neo4j. On each run:
1. Compute hash of each NotePlan file
2. Compare against stored hash
3. Only re-index changed files
4. Update hash after successful indexing

### Collection Strategy

| Collection | Level | Use |
|-----------|-------|-----|
| `app_actions_collection` | Whole-file | Legacy backward compat, coarse search |
| `sections_collection` | Section | Fine-grained retrieval, heading-aware |

Both use 4096-dim Qwen3 embeddings with COSINE distance.

## Claude Agent SDK

### Key Learnings

1. **`CLAUDE_CODE_STREAM_CLOSE_TIMEOUT`** — defaults to 60s, kills multi-tool queries. Set to 1800000ms (30 min).
2. **`tools=TOOL_NAMES`** restricts available tools; `allowed_tools` only controls permissions.
3. **Rate limiting** — CLI auto-retries 429s with backoff. Manifests as slow responses (60-300s), not errors. SDK emits `RateLimitEvent`.
4. **OAuth tokens** expire ~6 hours. Stored in named Docker volume. `make claude-agent-auth-seed` refreshes from host keychain.

### Multi-Turn Best Practice

Split complex workflows into separate turns (one tool per turn). Each turn completes within API response windows. Multi-turn sessions maintain context via `session_id`.

## Graph Schema

See [docs/GRAPH_SCHEMA.md](GRAPH_SCHEMA.md) for the complete schema reference (living doc).

Key additions for section indexing:
- `Section` node type (linked to Note via `HAS_SECTION`)
- `Section -[:CONTAINS]-> Entity` (section-level entity attribution)

## Observability

See [docs/OBSERVABILITY.md](OBSERVABILITY.md) for metrics, logging, and Grafana setup (living doc).

- Claude Agent exposes `/metrics` with `claude_agent_*` Prometheus namespace
- JSON structured logging to `build/logs/claude_agent.log`
- Grafana + Loki for centralized log search
