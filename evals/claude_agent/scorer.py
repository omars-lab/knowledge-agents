"""
Scorer for Claude Agent eval responses.

Dimensions:
- tool_selection: Did the agent use the expected tools?
- response_quality: Does the response address the question?
- session_continuity: For multi-turn, does context carry across turns?
- cost_efficiency: API cost relative to baseline
"""
from __future__ import annotations

from typing import Any


def score_response(
    result: dict[str, Any],
    expected: dict[str, Any],
    grading: dict[str, str],
) -> dict[str, float]:
    """Score an eval result against expectations.

    Returns dict of dimension -> score (0.0 to 1.0).
    """
    scores: dict[str, float] = {}

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

    # Overall quality (average of all scores)
    if scores:
        scores["overall"] = sum(scores.values()) / len(scores)

    return scores
