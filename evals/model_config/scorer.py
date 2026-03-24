"""
Scorer for model configuration evals — summarization quality.

Dimensions:
- conciseness: summary length relative to input (lower ratio = more concise)
- gold_similarity: word overlap with gold reference summary (ROUGE-L approx)
- completeness: LLM-graded (opt-in)
- faithfulness: LLM-graded (opt-in)
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _rouge_l_f1(candidate: str, reference: str) -> float:
    """Simple ROUGE-L F1 using longest common subsequence of words."""
    if not candidate or not reference:
        return 0.0

    cand_words = candidate.lower().split()
    ref_words = reference.lower().split()

    if not cand_words or not ref_words:
        return 0.0

    # LCS via DP
    m, n = len(cand_words), len(ref_words)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if cand_words[i - 1] == ref_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    lcs_len = dp[m][n]
    if lcs_len == 0:
        return 0.0

    precision = lcs_len / m
    recall = lcs_len / n
    f1 = 2 * precision * recall / (precision + recall)
    return f1


def _conciseness_score(summary: str, source: str) -> float:
    """Score conciseness as inverse of length ratio. 1.0 = maximally concise."""
    if not summary or not source:
        return 0.0
    ratio = len(summary.split()) / max(len(source.split()), 1)
    # Ideal: 5-15% of source length. Score 1.0 at 10%, dropping linearly.
    if ratio <= 0.15:
        return 1.0
    elif ratio <= 0.30:
        return 1.0 - (ratio - 0.15) / 0.15
    else:
        return max(0.0, 0.5 - (ratio - 0.30))


def _llm_grade(
    summary: str,
    source: str,
    dimension: str,
    rubric: str,
) -> float:
    """Use Claude Haiku to grade a specific quality dimension (1-5 → 0.0-1.0)."""
    try:
        import anthropic

        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": f"""Rate this summary on {dimension} (1-5):
Rubric: {rubric}
Source: {source[:500]}
Summary: {summary}
Output ONLY a JSON: {{"score": <1-5>}}""",
            }],
        )
        import json
        text = response.content[0].text.strip()
        parsed = json.loads(text)
        return max(0.0, min(1.0, (int(parsed["score"]) - 1) / 4.0))
    except Exception as e:
        logger.debug("LLM grading failed for %s: %s", dimension, e)
        return -1.0  # Sentinel: skip this dimension


def score_summary(
    summary: str,
    source_text: str,
    gold_summary: str = "",
    grading: dict[str, str] | None = None,
    llm_grading: bool = False,
) -> dict[str, float]:
    """Score a summary against multiple quality dimensions.

    Returns dict of dimension → score (0.0-1.0 for quality, raw for metrics).
    """
    scores: dict[str, float] = {}

    # Code-based scoring (always runs)
    scores["conciseness"] = _conciseness_score(summary, source_text)

    # Gold similarity (if gold summary provided)
    if gold_summary:
        scores["gold_similarity"] = _rouge_l_f1(summary, gold_summary)

    # Non-empty check
    scores["non_empty"] = 1.0 if summary.strip() else 0.0

    # LLM grading (opt-in, requires ANTHROPIC_API_KEY)
    if llm_grading and grading:
        for dimension, rubric in grading.items():
            grade = _llm_grade(summary, source_text, dimension, rubric)
            if grade >= 0:
                scores[dimension] = grade

    # Overall (average of 0-1 scores only)
    quality_scores = {k: v for k, v in scores.items() if 0 <= v <= 1}
    if quality_scores:
        scores["overall"] = sum(quality_scores.values()) / len(quality_scores)

    return scores
