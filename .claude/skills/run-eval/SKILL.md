---
name: run-eval
description: Execute Claude Agent eval suites or model config sweeps and present results
user_invocable: true
---

# /run-eval — Execute eval suites and show reports

Run the Claude Agent eval suite or model config eval sweep and present results.

## Two Eval Systems

### 1. Claude Agent Evals (tool selection, session management)

Tests the agent's ability to use the right tools, maintain sessions, and produce quality responses.

```bash
make claude-agent-eval              # Run all 4 datasets (10 test cases)
make claude-agent-eval-search       # Run only note_search dataset
make claude-agent-eval-graph        # Run only graph_building dataset
make claude-agent-eval-report       # Generate markdown report
```

**Datasets:** `evals/claude_agent/datasets/` (note_search, graph_building, multi_turn, tool_selection)
**Scoring:** tool_selection, response_contains, session_created/maintained, optional LLM grading
**Results:** `evals/claude_agent/results/` (JSON) + Langfuse traces

### 2. Model Config Evals (summarization quality comparison)

Compares different LM Studio model configurations for summarization quality with scores posted to Langfuse.

```bash
make model-eval                     # Run full sweep (all 5 configs × 10 cases)
make model-eval-config CONFIG="9b"  # Run specific config (substring match)
make model-eval-report              # Generate comparison report
```

**Configs** (`evals/model_config/configs.py`):
- Temperature sweep: 0.3, 0.5, 0.7
- Thinking mode: on vs off
- Model comparison: 35B-A3B vs 9B

**Scoring:** conciseness, non_empty, gold_similarity (ROUGE-L), optional LLM grading (completeness, faithfulness)
**Results:** `evals/model_config/results/` (JSON) + Langfuse (scores attached to traces)

## Workflow

### Running Agent Evals

Evals run in the Docker `test` container and talk to the `claude-agent` container via Docker networking (`http://claude-agent:8000`). This works both locally and on the Mac Studio — the `run` macro routes to the right host.

1. Ensure the stack is deployed: `/deploy` or `make deploy`
2. Ensure claude-agent is healthy: `make verify`
3. Run: `make claude-agent-eval`
4. Review: `make claude-agent-eval-report`
5. Check Langfuse for traces: http://localhost:3210 → filter by "chat" name

The eval targets use the `run` macro — when run from a MacBook, they SSH to the Mac Studio and execute there. Results are written to `evals/claude_agent/results/` (mounted volume).

### Running Model Config Evals

1. Ensure LM Studio has models loaded: `make lm-studio-status`
2. Ensure Langfuse is running: `make langfuse-up`
3. Run: `make model-eval`
4. Review: `make model-eval-report`
5. Compare in Langfuse:
   - Go to **Scores** page → filter by score name (conciseness, overall)
   - **Comment** column shows config name for comparison
   - Go to **Traces** → filter by name `model-eval-*` to see per-config traces
6. If winner found, update `docs/MODEL_DECISIONS.md` with results

### Adding New Test Cases

**Agent evals:** Edit JSON files in `evals/claude_agent/datasets/`
**Model evals:** Edit `evals/model_config/datasets/summarization.json` or pull new sections from Neo4j

### Adding New Model Configs

Edit `evals/model_config/configs.py` to add entries to `SUMMARIZATION_CONFIGS`.

## What's Working / Known Issues

**Working:**
- Agent evals: 10/10 passing (tool selection, session management)
- Model evals: full sweep across 5 configs with Langfuse score posting
- Qwen3.5-9B selected as winner (0.71 vs 0.64 for 35B)
- Langfuse captures 180+ scores for comparison

**Known issues:**
- Conciseness scores are moderate (~0.38-0.41) — summaries could be shorter
- No gold reference summaries in dataset (gold_summary field empty) — ROUGE-L not scored
- LLM grading requires ANTHROPIC_API_KEY env var — disabled by default
- Agent eval timeout can occur during rate-limited periods (increase with `--timeout 300`)
