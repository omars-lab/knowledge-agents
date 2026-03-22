"""
Eval runner for the Claude Agent.

Runs eval datasets against the agent API and scores responses.

Usage:
    python -m evals.claude_agent.runner                     # Run all datasets
    python -m evals.claude_agent.runner --dataset note_search  # Run specific dataset
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .scorer import score_response

logger = logging.getLogger(__name__)

DATASETS_DIR = Path(__file__).parent / "datasets"
RESULTS_DIR = Path(__file__).parent / "results"
AGENT_BASE_URL = "http://localhost:8004"
REQUEST_TIMEOUT = 300  # seconds per HTTP request
DELAY_BETWEEN_CASES = 3  # seconds between eval test cases (rate limit spacing)


def load_dataset(name: str) -> dict:
    """Load an eval dataset from JSON."""
    path = DATASETS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    with open(path) as f:
        return json.load(f)


def run_test_case(case: dict) -> dict:
    """Run a single eval test case against the agent API."""
    case_id = case["id"]
    turns = case["turns"]
    expected = case.get("expected", {})

    results = {
        "id": case_id,
        "description": case.get("description", ""),
        "turns": [],
        "tools_used": [],
        "session_id": None,
        "total_cost_usd": 0.0,
        "total_duration_ms": 0,
        "error": None,
    }

    session_id = None

    for i, turn in enumerate(turns):
        turn_start = time.time()
        try:
            payload = {"message": turn["input"]}
            if session_id:
                payload["session_id"] = session_id

            response = requests.post(
                f"{AGENT_BASE_URL}/api/v1/chat",
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            session_id = data.get("session_id")
            results["session_id"] = session_id
            tools = data.get("tools_used", [])
            results["tools_used"].extend(tools)

            cost = data.get("metadata", {}).get("cost_usd", 0) or 0
            results["total_cost_usd"] += cost

            turn_result = {
                "turn": i + 1,
                "input": turn["input"],
                "output": data.get("response", ""),
                "tools_used": tools,
                "duration_ms": int((time.time() - turn_start) * 1000),
                "cost_usd": cost,
            }
            results["turns"].append(turn_result)
            results["total_duration_ms"] += turn_result["duration_ms"]

        except Exception as e:
            results["error"] = str(e)
            logger.error("Error running case %s turn %d: %s", case_id, i + 1, e)
            break

    # Score the result
    results["scores"] = score_response(results, expected, case.get("grading", {}))
    results["tools_used"] = list(set(results["tools_used"]))

    return results


def run_dataset(name: str) -> dict:
    """Run all test cases in a dataset."""
    dataset = load_dataset(name)
    test_cases = dataset.get("test_cases", [])

    logger.info("Running eval dataset '%s' with %d test cases", name, len(test_cases))

    run_results = {
        "dataset": name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(test_cases),
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "total_cost_usd": 0.0,
        "cases": [],
    }

    for i, case in enumerate(test_cases):
        if i > 0 and DELAY_BETWEEN_CASES > 0:
            logger.info("  Waiting %ds between cases (rate limit spacing)...", DELAY_BETWEEN_CASES)
            time.sleep(DELAY_BETWEEN_CASES)
        logger.info("  Running case: %s", case["id"])
        result = run_test_case(case)
        run_results["cases"].append(result)

        if result.get("error"):
            run_results["errors"] += 1
        elif all(s >= 0.5 for s in result.get("scores", {}).values()):
            run_results["passed"] += 1
        else:
            run_results["failed"] += 1

        run_results["total_cost_usd"] += result.get("total_cost_usd", 0)

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_path = RESULTS_DIR / f"{name}_{ts}.json"
    with open(result_path, "w") as f:
        json.dump(run_results, f, indent=2)

    logger.info(
        "Dataset '%s': %d passed, %d failed, %d errors (cost: $%.4f)",
        name,
        run_results["passed"],
        run_results["failed"],
        run_results["errors"],
        run_results["total_cost_usd"],
    )

    return run_results


def main():
    """CLI entry point."""
    global AGENT_BASE_URL, DELAY_BETWEEN_CASES, REQUEST_TIMEOUT

    parser = argparse.ArgumentParser(description="Run Claude Agent evals")
    parser.add_argument(
        "--dataset",
        choices=["note_search", "graph_building", "multi_turn", "tool_selection"],
        help="Run a specific dataset (default: all)",
    )
    parser.add_argument("--url", default=AGENT_BASE_URL, help="Agent API URL")
    parser.add_argument("--delay", type=int, default=DELAY_BETWEEN_CASES, help="Seconds between test cases (default: 3)")
    parser.add_argument("--timeout", type=int, default=REQUEST_TIMEOUT, help="HTTP request timeout in seconds (default: 300)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    AGENT_BASE_URL = args.url
    DELAY_BETWEEN_CASES = args.delay
    REQUEST_TIMEOUT = args.timeout

    if args.dataset:
        datasets = [args.dataset]
    else:
        datasets = [p.stem for p in DATASETS_DIR.glob("*.json")]

    all_results = []
    for ds in datasets:
        try:
            result = run_dataset(ds)
            all_results.append(result)
        except FileNotFoundError:
            logger.warning("Dataset '%s' not found, skipping", ds)

    # Summary
    total_passed = sum(r["passed"] for r in all_results)
    total_failed = sum(r["failed"] for r in all_results)
    total_errors = sum(r["errors"] for r in all_results)
    total_cost = sum(r["total_cost_usd"] for r in all_results)

    print(f"\nEval Summary: {total_passed} passed, {total_failed} failed, {total_errors} errors")
    print(f"Total cost: ${total_cost:.4f}")

    if total_failed > 0 or total_errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
