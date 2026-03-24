# Model Decisions Log

> **Living Document** — update every time a model is changed. Record the decision, rationale, benchmarks, and links.

## Current Models

| Role | Model | Size | Key Metric | Since |
|------|-------|------|-----------|-------|
| **Embedding** | `text-embedding-qwen3-embedding-8b` | 4.68 GB | MTEB #1 (70.58) | 2026-03-23 |
| **Summarization** | `Qwen3.5-9B` (dense) | 6.55 GB | Eval score 0.71, 100% non-empty | 2026-03-24 |
| **Extraction (Graphiti)** | `Qwen3.5-35B-A3B` (MoE) | 22.07 GB | 5/5 episodes, structured JSON | 2026-03-24 |

## Where Models Are Configured

When changing a model, update these locations:

| Location | What to change | For |
|----------|---------------|-----|
| `config/litellm_config.yaml` | Add model route (`model_name` + `litellm_params`) | LiteLLM proxy routing |
| `src/knowledge_agents/services/summarizer.py` | `DEFAULT_MODEL` constant | Summarization pipeline default |
| `scripts/seed_sections.py` | `--summarize-model` default in argparse | CLI default |
| `docs/TECH_DESIGN.md` | Summarization/Embedding model section | Architecture docs |
| `docs/SECTION_INDEXING_PIPELINE.md` | Model requirements table | Pipeline docs |
| `docs/MODEL_DECISIONS.md` | This file — add a new decision entry | Decision log |
| `.claude/skills/model-select/SKILL.md` | "Current Model Inventory" table | Skill reference |

**For embedding model changes** (affects Qdrant collection):
- `config/litellm_config.yaml` — model route
- `src/knowledge_agents/claude_agent/config.py` — `litellm_proxy_embedding_model`
- All Qdrant collections must be re-indexed if dimensions change

## Decision Log

### 2026-03-24: Summarization Model → Qwen3.5-9B (replacing 35B-A3B)

**Previous:** `Qwen3.5-35B-A3B` (MoE, 22 GB, 85.3 MMLU-Pro)
**New:** `Qwen3.5-9B` (dense, 6.55 GB, 82.5 MMLU-Pro)

**Rationale (data-driven, from model config eval sweep):**

| Config | Conciseness | Non-Empty | Overall | Latency |
|--------|-----------|-----------|---------|---------|
| 35b-a3b t0.5 nothink | 0.38 | 0.90 | 0.64 | 16.8s |
| 35b-a3b t0.3 nothink | 0.38 | 0.90 | 0.64 | 14.1s |
| 35b-a3b t0.7 nothink | 0.38 | 0.90 | 0.64 | 15.1s |
| 35b-a3b t0.5 think | 0.40 | 0.90 | 0.65 | 16.6s |
| **9b t0.5 nothink** | **0.41** | **1.00** | **0.71** | 17.2s |

Key findings:
- 9B produces **higher quality summaries** (0.71 vs 0.64 overall)
- 9B has **perfect non-empty rate** (1.0 vs 0.9 — 35B occasionally produces empty output due to thinking overhead)
- 9B is **more concise** (0.41 vs 0.38)
- 9B uses **1/3 the RAM** (6.55 GB vs 22 GB)
- Temperature has **negligible effect** on 35B quality (0.64 across 0.3/0.5/0.7)
- Thinking mode adds **almost no value** for summarization (0.65 vs 0.64)

**Eval details:** 50 runs (5 configs × 10 note sections), scored on conciseness + non-empty. Results in Langfuse (180 scores) and `evals/model_config/results/`.

---

### 2026-03-23: Summarization Model → Qwen3.5-35B-A3B (MoE)

**Previous:** `ministral-3-14b-reasoning` (9.12 GB, ~65 MMLU-Pro est.)
**New:** `Qwen3.5-35B-A3B` (MoE, ~20 GB, 85.3 MMLU-Pro)

**Rationale:**
- 85.3 MMLU-Pro vs ~65 — ~30% quality improvement
- MoE architecture: only 3B params active per token → 5x faster throughput than 27B dense
- Surpasses previous-gen Qwen3-235B-A22B (22B active!) through better training
- Fits easily in 96GB RAM alongside 4.68GB embedding model

**Alternatives evaluated:**
| Model | MMLU-Pro | Size | Speed | Why not |
|-------|---------|------|-------|---------|
| Qwen3.5-9B | 82.5 | ~6 GB | Fast | Good alternative for smaller footprint |
| Qwen3.5-27B | Higher | ~17 GB | Moderate | Better quality but 5x slower than MoE |
| ministral-3-14b (prev) | ~65 | 9.12 GB | Fast | Outdated generation |

**Sources:**
- [Qwen3.5-9B tops benchmarks (XDA)](https://www.xda-developers.com/qwen-3-5-9b-tops-ai-benchmarks-not-how-pick-model/)
- [Qwen3.5 27B vs 35B-A3B (Vertu)](https://vertu.com/ai-tools/qwen-3-5-27b-vs-qwen-3-5-35b-a3b-which-local-llm-reigns-supreme/)
- [Qwen3.5 Local Guide (InsiderLLM)](https://insiderllm.com/guides/qwen35-local-guide-which-model-fits-your-gpu/)
- [Qwen3.5 Medium Models (DigitalApplied)](https://www.digitalapplied.com/blog/qwen-3-5-medium-model-series-benchmarks-pricing-guide)

**LM Studio artifact:** `lmstudio-community/Qwen3.5-35B-A3B-GGUF`

---

### 2026-03-23: Embedding Model → Keep Qwen3-Embedding-8B

**Decision:** No change. Already #1 on MTEB multilingual leaderboard.

**Current:** `text-embedding-qwen3-embedding-8b` (4.68 GB, 4096 dims, MTEB 70.58)

**Alternatives evaluated:**
| Model | MTEB | Dims | Size | Why not |
|-------|------|------|------|---------|
| Jina-Embeddings-v5-small | 67.0 MMTEB | 1024 | ~600 MB | Lower score, different dims → re-index 857 sections |
| Qwen3-Embedding-4B | ~69.45 | 4096 | ~2.5 GB | Slightly worse, marginal size savings |
| EmbeddingGemma-300M | Lower | 768 | ~200 MB | Too low quality for section retrieval |
| Qwen3-Embedding-0.6B | Lower | 4096 | ~400 MB | Much worse quality |

**Sources:**
- [Qwen3-Embedding-8B (HuggingFace)](https://huggingface.co/Qwen/Qwen3-Embedding-8B)
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [Qwen3 Embedding Blog](https://qwenlm.github.io/blog/qwen3-embedding/)
- [Jina Embeddings v5](https://jina.ai/news/jina-embeddings-v5-text-distilling-4b-quality-into-sub-1b-multilingual-embeddings/)

---

## Hardware Reference

**Mac Studio:** Apple M3 Ultra, 96 GB unified memory, 687 GB disk
**Max comfortable model load:** ~72 GB (75% of RAM)
**LM Studio:** v0.4.7+4 (updated from 0.3.39 to support Qwen3.5 MoE), GGUF format, bundled CLI

### Operational Notes

- **Thinking mode:** Qwen3.5 models use internal reasoning by default (~900 tokens overhead). Disable via `extra_body={"chat_template_kwargs": {"enable_thinking": false}}` and set `max_tokens=2000+`. Summarizer calls LM Studio directly (bypass LiteLLM) because LiteLLM strips `chat_template_kwargs`.
- **LM Studio CLI:** Use Staff Pick names for download: `lms get 'Qwen3.5-35B-A3B@q4_k_m' --yes`. Repo-style paths fail.
- **Version requirement:** LM Studio 0.4.7+ required for `qwen35moe` architecture.
