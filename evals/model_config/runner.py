"""
Model config eval runner — sweeps configurations and scores summarization quality.

Usage:
    python -m evals.model_config.runner                        # Run all configs
    python -m evals.model_config.runner --config 35b-a3b-t0.5  # Run specific config
    python -m evals.model_config.runner --llm-grading          # Enable LLM quality grading
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from knowledge_agents.services.summarizer import summarize_section
from knowledge_agents.types.section import SectionData
from knowledge_agents.utils.langfuse_trace import get_langfuse

from .configs import LM_STUDIO_KEY, LM_STUDIO_URL, SUMMARIZATION_CONFIGS
from .scorer import score_summary

logger = logging.getLogger(__name__)

DATASETS_DIR = Path(__file__).parent / "datasets"
RESULTS_DIR = Path(__file__).parent / "results"


def load_dataset(name: str) -> dict:
    path = DATASETS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    with open(path) as f:
        return json.load(f)


async def run_single_case(
    case: dict,
    config: dict,
    client: AsyncOpenAI,
) -> dict:
    """Run one test case with one config."""
    section = SectionData(
        file_path="eval",
        section_index=0,
        heading=case["section"]["heading"],
        heading_path=case["section"].get("heading_path", ""),
        raw_text=case["section"]["raw_text"],
        token_count=case["section"]["token_count"],
    )

    # Langfuse: create a trace for this eval case
    langfuse = get_langfuse()
    trace = None
    if langfuse:
        try:
            trace = langfuse.start_observation(
                name=f"model-eval-{config['name']}",
                input=case["section"]["raw_text"][:500],
                metadata={"config": config["name"], "case_id": case["id"], "model": config["model"]},
            )
        except Exception:
            pass

    start = time.monotonic()
    try:
        summary = await summarize_section(
            section,
            client,
            model=config["model"],
            max_summary_tokens=config["max_tokens"],
            temperature=config["temperature"],
            enable_thinking=config["enable_thinking"],
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        # Score
        scores = score_summary(
            summary=summary,
            source_text=case["section"]["raw_text"],
            gold_summary=case.get("gold_summary", ""),
            grading=case.get("grading", {}),
            llm_grading=bool(os.environ.get("ANTHROPIC_API_KEY")),
        )

        # Langfuse: update trace with output + post scores
        if trace:
            try:
                trace.update(output=summary[:500], metadata={"duration_ms": duration_ms, "scores": scores})
                trace.end()
                # Post scores with trace_id
                for score_name, score_val in scores.items():
                    if isinstance(score_val, (int, float)) and 0 <= score_val <= 1:
                        trace.score(name=score_name, value=score_val, comment=config["name"])
            except Exception as e:
                logger.debug("Langfuse score post failed: %s", e)

        return {
            "case_id": case["id"],
            "config": config["name"],
            "summary": summary,
            "duration_ms": duration_ms,
            "scores": scores,
            "error": None,
        }

    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error("Error on %s with %s: %s", case["id"], config["name"], e)
        if trace:
            try:
                trace.update(level="ERROR", status_message=str(e))
                trace.end()
            except Exception:
                pass
        return {
            "case_id": case["id"],
            "config": config["name"],
            "summary": "",
            "duration_ms": duration_ms,
            "scores": {},
            "error": str(e),
        }


async def run_config(
    dataset: dict,
    config: dict,
    delay: float = 1.0,
) -> dict:
    """Run all test cases for a single config."""
    client = AsyncOpenAI(base_url=LM_STUDIO_URL, api_key=LM_STUDIO_KEY)

    logger.info("Running config: %s (%d cases)", config["name"], len(dataset["test_cases"]))

    results = []
    for i, case in enumerate(dataset["test_cases"]):
        if i > 0 and delay > 0:
            await asyncio.sleep(delay)
        result = await run_single_case(case, config, client)
        results.append(result)
        status = "OK" if not result["error"] else "ERR"
        logger.info("  %s %s: %s (%dms)", status, case["id"], config["name"], result["duration_ms"])

    await client.close()

    # Aggregate
    ok_results = [r for r in results if not r["error"]]
    avg_duration = sum(r["duration_ms"] for r in ok_results) / max(len(ok_results), 1)

    # Average scores across cases
    score_sums: dict[str, float] = {}
    score_counts: dict[str, int] = {}
    for r in ok_results:
        for k, v in r["scores"].items():
            if isinstance(v, (int, float)):
                score_sums[k] = score_sums.get(k, 0) + v
                score_counts[k] = score_counts.get(k, 0) + 1
    avg_scores = {k: score_sums[k] / score_counts[k] for k in score_sums}

    return {
        "config": config,
        "total_cases": len(dataset["test_cases"]),
        "completed": len(ok_results),
        "errors": len(results) - len(ok_results),
        "avg_duration_ms": int(avg_duration),
        "avg_scores": avg_scores,
        "cases": results,
    }


async def main_async(args):
    dataset = load_dataset("summarization")

    configs = SUMMARIZATION_CONFIGS
    if args.config:
        configs = [c for c in configs if args.config in c["name"]]
        if not configs:
            logger.error("No config matching '%s'", args.config)
            sys.exit(1)

    all_results = []
    for config in configs:
        result = run_config(dataset, config, delay=args.delay)
        all_results.append(await result)

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_path = RESULTS_DIR / f"sweep_{ts}.json"
    with open(result_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    # Summary
    print(f"\n{'='*70}")
    print("Model Config Eval Results")
    print(f"{'='*70}")
    print(f"{'Config':<30} {'Cases':>6} {'Err':>4} {'Latency':>10} {'Overall':>8}")
    print("-" * 70)
    for r in all_results:
        overall = r["avg_scores"].get("overall", 0)
        print(f"{r['config']['name']:<30} {r['completed']:>6} {r['errors']:>4} {r['avg_duration_ms']:>8}ms {overall:>7.2f}")
    print(f"\nResults saved: {result_path}")

    langfuse = get_langfuse()
    if langfuse:
        from knowledge_agents.utils.langfuse_trace import flush
        flush()


def main():
    parser = argparse.ArgumentParser(description="Model config eval sweep")
    parser.add_argument("--config", help="Run specific config (substring match)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between cases (seconds)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
