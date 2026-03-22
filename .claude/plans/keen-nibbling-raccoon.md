# Refactor Eval Framework to Anthropic Success Criteria Patterns

## Context

Current eval framework is a functional smoke test: it checks tool invocation (substring match) and keyword presence in output. It passes 10/10 but doesn't measure **response quality, factual correctness, context retention, latency, or cost efficiency**. The `grading` field in test cases is documentation-only — never evaluated.

Anthropic's eval guidance recommends: specific/measurable criteria, LLM-based grading for nuanced quality, code-based grading for deterministic checks, and volume over perfection.

**Goal:** Upgrade the eval framework to measure what actually matters while keeping it fast and automated.

## Current Gaps (prioritized)

1. **No response quality scoring** — answers could be hallucinated and we'd never know
2. **Context retention is binary** — checks session_id exists, not if context was used
3. **No latency tracking** — can't detect performance regressions
4. **No error categorization** — timeouts, auth failures, and tool errors all lumped as "error"
5. **Grading config is dead code** — test cases have `grading` field but scorer ignores it

## Plan

### Step 1: Add LLM-based response quality grading to scorer

**File:** `evals/claude_agent/scorer.py`

Add a new `response_quality` dimension that uses Claude (via the Anthropic SDK) to grade responses on a 1-5 Likert scale. The grading prompt uses the test case's `grading` rubric (which already exists in every test case but is currently unused).

```python
def _grade_with_llm(output: str, grading: dict[str, str], input_text: str) -> float:
    """Use Claude to grade response quality on a 1-5 scale."""
    rubric = "\n".join(f"- {k}: {v}" for k, v in grading.items())
    prompt = f"""Rate this agent response on a scale of 1-5 based on these criteria:
{rubric}

User query: {input_text}
Agent response: {output}

Output only a JSON object: {{"score": <1-5>, "reasoning": "<brief explanation>"}}"""

    # Call Claude API directly (not via the agent SDK)
    response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",  # cheap/fast for grading
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    # Parse score, normalize to 0.0-1.0
```

Use `claude-haiku-4-5-20251001` for grading — cheap, fast, good enough for Likert scales. Only run LLM grading when `grading` config exists in the test case.

**Scoring:** Score 1→0.0, 2→0.25, 3→0.5, 4→0.75, 5→1.0

### Step 2: Add latency and cost tracking to scorer

**File:** `evals/claude_agent/scorer.py`

Add `latency` and `cost` dimensions that track absolute values (not pass/fail). These are informational metrics stored in results for regression detection.

```python
# In score_response():
if result.get("total_duration_ms"):
    scores["latency_ms"] = result["total_duration_ms"]  # raw value, not 0-1
if result.get("total_cost_usd"):
    scores["cost_usd"] = result["total_cost_usd"]  # raw value, not 0-1
```

Exclude these from the `overall` average (they're not 0-1 scores).

### Step 3: Categorize errors in runner

**File:** `evals/claude_agent/runner.py`

Replace the generic `error` field with structured error categorization:

```python
except requests.Timeout:
    results["error"] = {"type": "timeout", "message": "..."}
except requests.HTTPError as e:
    status = e.response.status_code
    if status == 503:
        results["error"] = {"type": "transport_error", "message": "..."}
    elif status == 401:
        results["error"] = {"type": "auth_error", "message": "..."}
    else:
        results["error"] = {"type": "http_error", "status": status, "message": "..."}
except Exception as e:
    results["error"] = {"type": "unknown", "message": str(e)}
```

### Step 4: Add context retention scoring for multi-turn

**File:** `evals/claude_agent/scorer.py`

For multi-turn cases (`session_maintained: true`), use LLM grading to check if later turns actually reference content from earlier turns:

```python
def _grade_context_retention(turns: list[dict]) -> float:
    """LLM grades whether later turns use context from earlier turns."""
    if len(turns) < 2:
        return 1.0
    # Build conversation transcript, ask Claude to rate context usage 1-5
```

### Step 5: Upgrade report with richer metrics

**File:** `evals/claude_agent/report.py`

Add to the markdown report:
- Per-case latency and cost columns
- Error breakdown by type (timeout, transport, auth, http)
- Response quality scores (when LLM grading is available)
- Comparison with previous run (if a prior result file exists)

### Step 6: Add edge case test cases

**Files:** `evals/claude_agent/datasets/*.json`

Add edge cases to existing datasets:
- `note_search.json`: Add `read-004` with a nonexistent file path (expects graceful error handling)
- `tool_selection.json`: Add `tool-004` with an ambiguous query (tests tool reasoning)
- `graph_building.json`: Add `graph-003` with an empty note (expects graceful "no entities found")

### Step 7: Add ANTHROPIC_API_KEY config for LLM grading

**File:** `evals/claude_agent/scorer.py`, `evals/claude_agent/runner.py`

LLM grading needs an Anthropic API key. Use `ANTHROPIC_API_KEY` from environment (already used by the container). Add `--llm-grading` flag to runner to enable/disable (disabled by default for speed).

```bash
# Fast run (code-based grading only)
python -m evals.claude_agent.runner

# Full run with LLM quality grading
python -m evals.claude_agent.runner --llm-grading
```

## Critical Files

| File | Change |
|------|--------|
| `evals/claude_agent/scorer.py` | LLM grading, latency/cost tracking, context retention |
| `evals/claude_agent/runner.py` | Error categorization, --llm-grading flag |
| `evals/claude_agent/report.py` | Richer metrics table, error breakdown |
| `evals/claude_agent/datasets/*.json` | Edge case test cases |
| `requirements-claude-agent.txt` | Add `anthropic` package for LLM grading |

## Verification

1. Unit tests: `conda run -n knowledge-agents pytest tst/unit/claude_agent/ -v -m unit`
2. Fast eval (no LLM grading): `python -m evals.claude_agent.runner`
3. Full eval with grading: `ANTHROPIC_API_KEY=... python -m evals.claude_agent.runner --llm-grading`
4. Report: `python -m evals.claude_agent.report` — verify new columns appear
5. Edge cases: verify graceful error handling, not crashes

## Design Decisions

- **Haiku for grading, not Opus** — 10x cheaper, fast enough for Likert scales, different model than the one being evaluated (best practice)
- **LLM grading opt-in** — default runs are fast/free (code-based only), `--llm-grading` adds quality scoring at ~$0.001/case
- **Latency/cost as raw values** — not normalized to 0-1, excluded from overall score, used for regression tracking
- **Grading rubrics reuse existing `grading` field** — no test case changes needed for LLM grading to work
