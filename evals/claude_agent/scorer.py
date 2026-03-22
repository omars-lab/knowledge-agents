"""
Scorer for Claude Agent eval responses.

Dimensions:
- tool_selection: Did the agent use the expected tools?
- response_contains / response_not_contains: Keyword checks
- session_created / session_maintained: Session management
- response_quality: LLM-graded quality (opt-in, uses grading rubric)
- context_retention: LLM-graded multi-turn context usage (opt-in)
- latency_ms / cost_usd: Raw metrics (not included in overall score)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# LLM grading client — initialized lazily on first use
_anthropic_client = None
_GRADING_MODEL = "claude-haiku-4-5-20251001"


def _get_anthropic_client():
    """Lazy-init Anthropic client for LLM grading."""
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic

        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _llm_grade_quality(
    output: str,
    grading: dict[str, str],
    input_text: str,
) -> float:
    """Use Claude to grade response quality on a 1-5 Likert scale.

    Returns normalized score (0.0 to 1.0).
    """
    rubric = "\n".join(f"- {k}: {v}" for k, v in grading.items())
    prompt = f"""Rate this agent response on a scale of 1-5 based on these criteria:
{rubric}

User query: {input_text}
Agent response: {output}

Think briefly about each criterion, then output a JSON object:
{{"score": <1-5>, "reasoning": "<one sentence>"}}
Output ONLY the JSON object, nothing else."""

    try:
        client = _get_anthropic_client()
        response = client.messages.create(
            model=_GRADING_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        parsed = json.loads(text)
        score = int(parsed["score"])
        logger.debug("LLM grade: %d/5 — %s", score, parsed.get("reasoning", ""))
        return max(0.0, min(1.0, (score - 1) / 4.0))
    except Exception as e:
        logger.warning("LLM grading failed: %s", e)
        return -1.0  # Sentinel: grading failed, excluded from overall


def _llm_grade_context_retention(turns: list[dict]) -> float:
    """Use Claude to grade whether later turns reference earlier context.

    Returns normalized score (0.0 to 1.0).
    """
    if len(turns) < 2:
        return 1.0

    transcript = ""
    for t in turns:
        transcript += f"User: {t.get('input', '')}\nAssistant: {t.get('output', '')[:500]}\n\n"

    prompt = f"""Rate how well this multi-turn conversation maintains context on a scale of 1-5:

{transcript}

Criteria:
- Does the assistant reference information from earlier turns?
- Does the conversation build logically across turns?
- Would the later responses make sense without the earlier turns?

1: Completely ignores prior context
3: Acknowledges context but doesn't use it deeply
5: Seamlessly builds on all prior context

Output ONLY a JSON object: {{"score": <1-5>, "reasoning": "<one sentence>"}}"""

    try:
        client = _get_anthropic_client()
        response = client.messages.create(
            model=_GRADING_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        parsed = json.loads(text)
        score = int(parsed["score"])
        logger.debug("Context retention: %d/5 — %s", score, parsed.get("reasoning", ""))
        return max(0.0, min(1.0, (score - 1) / 4.0))
    except Exception as e:
        logger.warning("Context retention grading failed: %s", e)
        return -1.0


def score_response(
    result: dict[str, Any],
    expected: dict[str, Any],
    grading: dict[str, str],
    *,
    llm_grading: bool = False,
) -> dict[str, float]:
    """Score an eval result against expectations.

    Returns dict of dimension -> score (0.0 to 1.0 for quality scores,
    raw values for latency_ms and cost_usd).

    Args:
        result: The eval run result dict
        expected: Expected outcomes from the test case
        grading: Rubric criteria from the test case (used by LLM grading)
        llm_grading: If True, run LLM-based quality and context grading
    """
    scores: dict[str, float] = {}

    # --- Code-based grading (always runs) ---

    # Tool selection score
    expected_tools = expected.get("tools_used", [])
    actual_tools = result.get("tools_used", [])
    if expected_tools:
        matched = sum(
            1
            for et in expected_tools
            if any(et in at for at in actual_tools)
        )
        scores["tool_selection"] = matched / len(expected_tools)
    else:
        scores["tool_selection"] = 1.0

    # Response quality — check output_contains / output_not_contains
    last_turn = result.get("turns", [{}])[-1] if result.get("turns") else {}
    output = last_turn.get("output", "").lower()

    contains = expected.get("output_contains", [])
    not_contains = expected.get("output_not_contains", [])

    if contains:
        matched = sum(1 for c in contains if c.lower() in output)
        scores["response_contains"] = matched / len(contains)
    else:
        scores["response_contains"] = 1.0

    if not_contains:
        violations = sum(1 for nc in not_contains if nc.lower() in output)
        scores["response_not_contains"] = 1.0 - (violations / len(not_contains))
    else:
        scores["response_not_contains"] = 1.0

    # Session continuity — check session_created / session_maintained
    if expected.get("session_created"):
        scores["session_created"] = 1.0 if result.get("session_id") else 0.0
    if expected.get("session_maintained"):
        scores["session_maintained"] = 1.0 if result.get("session_id") else 0.0

    # --- Raw metrics (not included in overall) ---

    if result.get("total_duration_ms"):
        scores["latency_ms"] = float(result["total_duration_ms"])
    if result.get("total_cost_usd"):
        scores["cost_usd"] = result["total_cost_usd"]

    # --- LLM-based grading (opt-in) ---

    if llm_grading and grading and result.get("turns"):
        # Response quality (uses grading rubric from test case)
        last_input = result["turns"][-1].get("input", "")
        last_output = result["turns"][-1].get("output", "")
        if last_output:
            quality = _llm_grade_quality(last_output, grading, last_input)
            if quality >= 0:
                scores["response_quality"] = quality

        # Context retention (multi-turn only)
        if expected.get("session_maintained") and len(result.get("turns", [])) >= 2:
            retention = _llm_grade_context_retention(result["turns"])
            if retention >= 0:
                scores["context_retention"] = retention

    # --- Overall (average of 0-1 scores only, exclude raw metrics) ---

    quality_scores = {
        k: v for k, v in scores.items()
        if k not in ("latency_ms", "cost_usd") and v >= 0
    }
    if quality_scores:
        scores["overall"] = sum(quality_scores.values()) / len(quality_scores)

    return scores
