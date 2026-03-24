---
name: model-select
description: "Hardware-aware LM Studio model recommendations. Inspects Mac Studio specs, evaluates installed models, searches for better alternatives via web benchmarks, and recommends the best model for embedding, summarization, code, or chat tasks."
---

# Model Select

You are a hardware-aware model selection assistant. Inspect Mac Studio hardware, evaluate installed LM Studio models, search for better alternatives via web, and recommend the optimal model for a given task.

## When to Use

- Before running the section indexing pipeline (`make seed-sections-summarize`)
- When setting up a new task type (code generation, translation, RAG, etc.)
- When a model feels slow or produces low-quality results
- When you want to know what's available vs what's installed

## Workflow

### Step 1: Inspect Hardware

SSH to the Mac Studio and gather specs:
```bash
ssh -o ConnectTimeout=5 mac-studio "
  echo '=== Hardware ==='
  sysctl -n machdep.cpu.brand_string 2>/dev/null || echo 'Apple Silicon'
  echo 'RAM:' \$(sysctl -n hw.memsize | awk '{printf \"%.0f GB\", \$1/1024/1024/1024}')
  system_profiler SPHardwareDataType 2>/dev/null | grep -E 'Chip|Memory|Model Name'
  echo ''
  echo '=== Disk ==='
  df -h / | tail -1 | awk '{print \"Available:\", \$4}'
"
```

**Key constraint:** Total loaded model size must stay under ~75% of RAM for good performance. On a 96GB Mac Studio, that's ~72GB max across all loaded models.

### Step 2: List Installed Models

```bash
ssh -o ConnectTimeout=5 mac-studio "'/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms' ls"
```

Note the model sizes and types (LLM vs Embedding).

### Step 3: Check Currently Loaded Models

```bash
ssh -o ConnectTimeout=5 mac-studio "'/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms' ps"
```

Check RAM headroom: loaded models size vs total RAM.

### Step 4: Determine Task Requirements

For the user's stated task, determine:

| Task Type | Key Metric | Model Category | Typical Size Range |
|-----------|-----------|----------------|-------------------|
| **Embedding** (semantic search) | Retrieval quality, dimensions, speed | Embedding model | 0.1-8 GB |
| **Summarization** (note indexing) | Output quality, speed, concurrency | Chat/instruct model | 5-30 GB |
| **Code generation** | Code quality, instruction following | Code-specialized | 10-30 GB |
| **General chat** | Response quality, reasoning | General instruct | 8-70 GB |
| **Entity extraction** | Structured output, accuracy | Instruct model | 5-15 GB |

### Step 5: Search LM Studio Catalog FIRST (installable models only)

**IMPORTANT:** Only recommend models that are actually installable via LM Studio. Search the catalog first, then use web search to rank the available options.

Search the LM Studio catalog for candidate models by task type:

```bash
# Search by task-relevant keywords — check what's ACTUALLY available
# Use --quiet to suppress interactive prompts (output shows selection list)
ssh -o ConnectTimeout=5 mac-studio "'/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms' get '<search-term>' --quiet 2>&1" | head -20

# To download: use Staff Pick name + @quantization (NOT repo paths)
# Example: 'Qwen3.5-35B-A3B@q4_k_m' NOT 'lmstudio-community/Qwen3.5-35B-A3B-GGUF'
```

**Search terms by task type:**
- **Embedding:** `embedding`, `qwen3-embedding`, `jina-embedding`, `nomic-embed`
- **Summarization/chat:** `qwen3.5`, `qwen3`, `llama`, `mistral`, `phi`
- **Code:** `coder`, `devstral`, `deepseek-coder`

Run multiple searches to build a candidate list. Only models that appear in these results can be recommended.

### Step 6: Research Candidates via Web (rank available models)

Now that you have a list of **installable** models, use web search to rank them by quality:

**For embeddings:**
- Search: `"<model-name> MTEB retrieval benchmark score"` for each candidate
- Check: [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)

**For summarization/chat:**
- Search: `"<model-name> benchmark MMLU quality 2026"` for each candidate
- Check: [Open LLM Leaderboard](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard)

**For code:**
- Search: `"<model-name> HumanEval pass@1 benchmark"` for each candidate

Only include benchmark data for models confirmed available in LM Studio catalog.

### Step 7: Evaluate Fit

For each candidate model, evaluate:

1. **Size vs RAM**: Model size (quantized) must fit with other models you need loaded
   - Rule of thumb: `params * 0.6 GB` for Q4_K_M, `params * 1.0 GB` for Q8_0
   - Leave 25% RAM free for OS + inference buffers

2. **Quality vs speed trade-off**:
   - More parameters = better quality but slower
   - MoE models (e.g., Qwen3.5-35B-A3B) have high quality with fast inference (only active params matter)

3. **Quantization** — pick based on RAM budget:

   | Quantization | Quality Retention | Size vs FP16 | When to use |
   |-------------|------------------|--------------|-------------|
   | **Q8_0** | ~99% | ~50% | Have lots of RAM, want near-lossless |
   | **Q6_K** | ~98% | ~43% | Good RAM headroom, quality-sensitive tasks |
   | **Q5_K_M** | ~95% | ~37% | Sweet spot when RAM allows |
   | **Q4_K_M** | ~92% | ~30% | **Default choice** — best quality/size balance |
   | **Q3_K_M** | ~85% | ~25% | Tight on RAM, still usable |
   | **IQ2_M** | ~75% | ~18% | Extreme compression, noticeable quality loss |

   **For our Mac Studio (96GB):** Use Q5_K_M or Q4_K_M. We have plenty of RAM so prefer Q5_K_M for slightly better quality. Only drop to Q4_K_M if loading multiple large models simultaneously.

   **How to check available quantizations:**
   ```bash
   # lms get shows available variants when you specify model@quantization
   ssh mac-studio "'/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms' get '<model>@q5_k_m' --quiet 2>&1" | head -5
   ```

4. **Runtime framework** (GGUF vs MLX):

   | Framework | Format | Speed on Apple Silicon | Availability |
   |-----------|--------|----------------------|-------------|
   | **GGUF** (llama.cpp) | `.gguf` | Baseline | Most models available |
   | **MLX** (Apple native) | `.safetensors` | **20-30% faster** | Fewer models, growing |

   **Recommendation:** Prefer GGUF for compatibility (LM Studio uses llama.cpp backend). Consider MLX variants (`mlx-community/` prefix in catalog) if available for your model — they're faster on Apple Silicon but may have fewer quantization options.

   **How to search MLX variants:**
   ```bash
   ssh mac-studio "'/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms' get '<model>' --mlx --quiet 2>&1" | head -10
   ```

5. **Context window**: Longer context = more RAM. 8K context is usually sufficient for note sections. 32K+ contexts can add 2-4 GB of RAM usage.

### Step 8: Present Recommendation

Format your recommendation as:

```
## Model Recommendation for [TASK]

### Hardware
- Chip: [chip]
- RAM: [total]GB ([available]GB free after currently loaded models)

### Current Model
- [current model name] ([size]GB)
- [assessment: adequate/outdated/wrong-task]

### Recommended Model
- **[model name]** ([size]GB, [quantization])
- Why: [1-2 sentence justification]
- Benchmark: [relevant score if found]
- LM Studio availability: [available/not found]

### Alternative
- [alternative model] ([size]GB) — [trade-off vs recommended]

### Installation
To install and load:
\`\`\`bash
# Download — use Staff Pick name + @quantization (case-sensitive!)
# Format: 'ModelName@quantization' e.g. 'Qwen3.5-35B-A3B@q4_k_m'
# DO NOT use repo paths like 'lmstudio-community/...' — they fail with lms CLI
ssh mac-studio "'/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms' get '[ModelName]@[quantization]' --yes"

# Load after download completes
ssh mac-studio "'/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms' load --yes '[model-identifier]'"
\`\`\`

**Common quantization suffixes:** `@q4_k_m` (default), `@q5_k_m`, `@q8_0`, `@q3_k_m`

### Configuration (IMPORTANT — do this after loading)

After loading a model, configure it for your task. Key settings:

#### Thinking / Reasoning Mode

Qwen3 and Qwen3.5 models have built-in reasoning ("thinking") that runs before content output. This uses ~800-1000 extra tokens per response.

| Setting | When | How |
|---------|------|-----|
| **Thinking ON** | Complex reasoning, math, code analysis | Default behavior (no config needed) |
| **Thinking OFF** | Batch summarization, simple Q&A, fast responses | See below |

**To disable thinking via API** (for batch summarization):
\`\`\`python
# Call LM Studio DIRECTLY (not through LiteLLM — it strips this param)
response = await client.chat.completions.create(
    model="qwen3.5-35b-a3b",
    max_tokens=2000,  # MUST be high — model uses ~900 tokens reasoning overhead
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    messages=[...],
)
\`\`\`

**To disable thinking via LM Studio GUI:**
1. Go to My Models → select model → Inference sidebar
2. Scroll to Prompt Template (Jinja)
3. Add `{%- set enable_thinking = false %}` as the first line
4. Reload model

**WARNING:** Even with `enable_thinking=false`, Qwen3.5 still uses ~900 tokens of internal reasoning. Set `max_tokens=2000+` for summarization (actual summary is ~50-100 tokens).

#### Load Options (CLI)

\`\`\`bash
# Context length (default: model max, reduce to save RAM)
lms load --yes 'model-name' --context-length 8192

# Parallel inference (concurrent requests, reduces per-request speed)
lms load --yes 'model-name' --parallel 4

# GPU offload (Apple Silicon: usually auto, 'max' for full GPU)
lms load --yes 'model-name' --gpu max

# TTL (auto-unload after N seconds of inactivity)
lms load --yes 'model-name' --ttl 3600

# Estimate RAM before loading
lms load --yes 'model-name' --estimate-only
\`\`\`

#### Sampling Parameters by Task

| Task | Temperature | Top-P | Max Tokens | Notes |
|------|-------------|-------|------------|-------|
| Summarization | 0.3-0.5 | 0.9 | 2000 | Low temp for factual, consistent summaries |
| Entity extraction | 0.1-0.3 | 0.9 | 1000 | Very low temp for structured JSON output |
| General chat | 0.7-0.9 | 0.95 | 4000 | Higher temp for creative, varied responses |
| Code generation | 0.2-0.4 | 0.95 | 4000 | Low temp for correct code |

### Files to Update (MANDATORY after model change)
After changing a model, update ALL of these:
\`\`\`
config/litellm_config.yaml           — Add model route (model_name + litellm_params)
src/knowledge_agents/services/summarizer.py — DEFAULT_MODEL (for summarization)
scripts/seed_sections.py              — --summarize-model default in argparse
docs/MODEL_DECISIONS.md               — Add decision entry with rationale + links
docs/TECH_DESIGN.md                   — Model section
docs/SECTION_INDEXING_PIPELINE.md     — Model requirements table
.claude/skills/model-select/SKILL.md  — Current Model Inventory table (this file)
\`\`\`
For embedding model changes, also update:
\`\`\`
src/knowledge_agents/claude_agent/config.py — litellm_proxy_embedding_model
\`\`\`
And re-index all Qdrant collections if dimensions change.
```

## Current Model Inventory

Last updated: 2026-03-23. See `docs/MODEL_DECISIONS.md` for full decision log with links.

**Active models (used by pipelines):**

| Role | Model | Size | Key Metric |
|------|-------|------|-----------|
| **Embedding** | `text-embedding-qwen3-embedding-8b` | 4.68 GB | MTEB #1 (70.58) |
| **Summarization** | `Qwen3.5-9B` (dense) | 6.55 GB | Eval score 0.71, 100% non-empty |

**Other installed models:**

| Model | Size | Type | Notes |
|-------|------|------|-------|
| `Qwen3.5-35B-A3B` | 22.07 GB | Chat (MoE) | Previous summarization model (eval: 0.64, 90% non-empty) |
| `text-embedding-nomic-embed-text-v1.5` | 84 MB | Embedding | Backup, 768 dims |
| `ministral-3-14b-reasoning` | 9.12 GB | Chat | Outdated generation |
| `openai/gpt-oss-20b` | 12.10 GB | Chat | General |
| `qwen/qwen3-coder-30b` | 17.19 GB | Code | MoE, fast inference |
| `mistralai/devstral-small-2-2512` | 14.12 GB | Code | Coding-focused |

**Last eval sweep:** 2026-03-24 — 50 runs (5 configs × 10 sections), 180 Langfuse scores. See `docs/MODEL_DECISIONS.md`.

**Hardware:** M3 Ultra, 96 GB unified memory

## Models Worth Investigating

From LM Studio catalog search (2026-03-23):

| Model | Type | Why investigate |
|-------|------|----------------|
| `Qwen3 8B` | Chat | Latest gen, fast, good summarization |
| `Qwen3 30B A3B (MoE)` | Chat | 3B active params, high quality at MoE speed |
| `Qwen3.5 9B` / `Qwen3.5 27B` | Chat | Newest generation, may outperform all above |
| `jina-embeddings-v5-text-small-retrieval` | Embedding | SOTA retrieval, but different dims than Qwen3 |

## Use Case Research Guide

When evaluating models for a specific use case, research these dimensions:

### Embedding Models
- **Benchmark**: MTEB Retrieval score (higher = better at finding relevant docs)
- **Search**: `"<model-name> MTEB retrieval benchmark"` or check the leaderboard
- **Key factors**: Dimensions (higher ≠ always better), speed, max sequence length
- **For NotePlan sections**: Prioritize retrieval quality over classification or clustering
- **Watch out for**: Instruction-tuned embedding models that need query prefixes (e.g., "query:" / "passage:")

### Summarization Models
- **Benchmark**: MT-Bench, AlpacaEval, or manual quality assessment
- **Search**: `"<model-name> summarization quality benchmark 2026"`
- **Key factors**: Instruction following, output length control, factual accuracy
- **For note sections**: Model should produce 1-2 sentence summaries that capture key facts, not verbose restatements
- **Watch out for**: Models that hallucinate details not in the source text

### Code Generation Models
- **Benchmark**: HumanEval, MBPP, SWE-bench
- **Search**: `"<model-name> HumanEval pass@1"`
- **Key factors**: Multi-language support, long context for repo-level understanding
- **Watch out for**: Models fine-tuned on narrow codebases (may fail on unfamiliar patterns)

### Entity Extraction Models
- **Benchmark**: NER benchmarks, structured output quality
- **Search**: `"<model-name> structured JSON output quality"`
- **Key factors**: Ability to output valid JSON, follow schemas, handle edge cases
- **For knowledge graphs**: Model should extract entities AND relationships with correct types
- **Watch out for**: Models that produce malformed JSON or miss relationship directionality

### General Reasoning / Chat
- **Benchmark**: MMLU, HellaSwag, ARC, TruthfulQA
- **Search**: `"<model-name> MMLU benchmark 2026"`
- **Key factors**: Reasoning depth, context utilization, instruction following
- **Watch out for**: Benchmark-gamed models that perform well on tests but poorly on real tasks

### MoE Models (Mixture of Experts)
- **Key insight**: Only a fraction of parameters are active per token (e.g., 30B total but 3B active)
- **Speed**: Near-small-model speed with large-model quality
- **RAM**: Still need to load the full model into memory, but inference is fast
- **Best for**: Batch processing where quality matters but speed is also important
- **Examples**: Qwen3 30B A3B, Qwen3.5 397B A17B, Mixtral

### How to Compare Two Models

1. **Web search** both models + your use case: `"Qwen3 8B vs ministral 14B summarization quality"`
2. **Check release dates** — newer models generally outperform older ones at the same size
3. **Check quantization availability** — prefer models with official GGUF releases over community-quantized
4. **Test locally**: Load both, run 10 identical prompts, compare outputs side-by-side
5. **Check community feedback**: Search Reddit r/LocalLLaMA, HuggingFace discussions

## Key References

- **MTEB Leaderboard**: https://huggingface.co/spaces/mteb/leaderboard (embedding benchmarks)
- **Open LLM Leaderboard**: https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard
- **LM Studio models**: Search via `lms get <query>` on Mac Studio
- **Hardware guide**: https://docs.lmstudio.ai/hardware
