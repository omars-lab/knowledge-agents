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

### Summarization: Qwen3.5-9B (dense)

| Property | Value |
|----------|-------|
| Model | `qwen3.5-9b` |
| Size | 6.55 GB (Q4_K_M) |
| Architecture | Dense — 9B params, all active |
| MMLU-Pro | 82.5 |
| Eval Score | 0.71 overall (best of 5 configs tested) |
| Use case | Batch note summarization |

**Why (data-driven):** Eval sweep across 5 configs (50 runs total) showed 9B produces better summaries than 35B-A3B MoE (0.71 vs 0.64 overall). The 35B model has a 10% empty-output rate due to thinking mode overhead; 9B has 0%. Uses 1/3 the RAM (6.55 vs 22 GB).

**Decision date:** 2026-03-24

**Previous model:** `Qwen3.5-35B-A3B` (MoE, 22 GB) — replaced because eval data showed lower quality despite higher benchmarks. Thinking mode overhead was the root cause.

**Full eval results:** See `docs/MODEL_DECISIONS.md` and Langfuse (180 scores across 5 configs).

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

## Graph Engine: Graphiti

See [docs/GRAPH_SCHEMA.md](GRAPH_SCHEMA.md) for the complete schema reference, and [docs/GRAPHITI_INTEGRATION.md](GRAPHITI_INTEGRATION.md) for the full integration plan and use cases.

**Engine:** [Graphiti](https://github.com/getzep/graphiti) — temporal knowledge graph with automatic entity extraction, deduplication, and hybrid search.

**Key capabilities over previous hand-built pipeline:**
- Temporal fact validity (`valid_at`, `invalid_at`, `expired_at` on every edge)
- Automatic entity resolution (LLM-powered dedup)
- Hybrid search (semantic + keyword + graph traversal)
- Episode provenance (every entity traces back to source notes)
- Community detection (auto-clustering)

**Models:** Qwen3.5-35B-A3B for extraction (structured JSON), Qwen3-Embedding-8B for embeddings. All local on Mac Studio.

## Observability

See [docs/OBSERVABILITY.md](OBSERVABILITY.md) for the full stack reference (living doc).

**Two observability paths:**
- **LLM Tracing:** Langfuse v3 (self-hosted) at `localhost:3210` — captures every agent chat with input/output/cost/tools/duration. Backed by ClickHouse + Redis + MinIO.
- **Logs:** Loki + Grafana at `localhost:3001` — container log aggregation via Docker logging driver.

**Langfuse integration:**
- Python SDK v4 with graceful degradation (no-op if Langfuse is down)
- Traces from: Claude Agent chat, summarizer batch, tool calls
- Pre-seeded API keys: `pk-lf-knowledge` / `sk-lf-knowledge`
- Gotcha: v4 `end()` doesn't accept output — call `update(output=...)` then `end()`
