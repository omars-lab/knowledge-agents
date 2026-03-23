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

### Step 5: Search for Better Models

Use web search to find the latest benchmarks and recommendations. Key searches:

**For embeddings:**
- Search: `"best embedding model 2025 2026 GGUF local" MTEB benchmark`
- Check: [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard) for retrieval benchmarks
- Consider: Jina v5, Qwen3 Embedding, Nomic Embed, BGE

**For summarization/chat:**
- Search: `"best local LLM summarization 2026 GGUF Apple Silicon" benchmark`
- Check: [Open LLM Leaderboard](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard)
- Consider: Qwen3 (latest gen), Llama 4, Mistral, Phi

**For code:**
- Search: `"best local code model 2026 GGUF" HumanEval benchmark`
- Consider: Qwen3-Coder, DeepSeek Coder, Devstral

### Step 6: Search LM Studio Catalog

For each recommended model, check if it's available in LM Studio:

```bash
# Interactive search (will show available models)
ssh -o ConnectTimeout=5 mac-studio "'/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms' get '<model-name>' --quiet 2>&1" | head -20
```

Note: `lms get` is interactive — it shows a selection list. Look at the output to see if the model exists.

### Step 7: Evaluate Fit

For each candidate model, evaluate:

1. **Size vs RAM**: Model size (quantized) must fit with other models you need loaded
   - Q4_K_M quantization ≈ ~60% of full model size
   - Rule of thumb: `params * 0.6 GB` for Q4_K_M

2. **Quality vs speed trade-off**:
   - More parameters = better quality but slower
   - MoE models (e.g., Qwen3-30B-A3B) have high quality with fast inference (only active params matter)

3. **Quantization**: For Mac Studio with 96GB, prefer Q4_K_M or Q5_K_M (good quality/size balance)

4. **Context window**: Longer context = more RAM. 8K context is usually sufficient for note sections.

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
ssh mac-studio "'/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms' get '[model-name]' --yes"
ssh mac-studio "'/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms' load --yes '[model-path]'"
\`\`\`
```

## Current Model Inventory

Last updated: 2026-03-23

| Model | Size | Type | Task | Notes |
|-------|------|------|------|-------|
| `text-embedding-qwen3-embedding-8b` | 4.68 GB | Embedding | Section/file embeddings | 4096 dims, primary embedding model |
| `text-embedding-nomic-embed-text-v1.5` | 84 MB | Embedding | (backup) | 768 dims, fast but lower quality |
| `ministral-3-14b-reasoning` | 9.12 GB | Chat | Summarization | Good for batch note summarization |
| `openai/gpt-oss-20b` | 12.10 GB | Chat | General | Alternative summarization model |
| `qwen/qwen3-coder-30b` | 17.19 GB | Code | Code generation | MoE, fast inference |
| `mistralai/devstral-small-2-2512` | 14.12 GB | Code | Code generation | Coding-focused |

**Total installed:** 57.29 GB
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
