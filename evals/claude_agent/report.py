"""
Generate eval report from latest results.

Usage:
    python -m evals.claude_agent.report
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"


def find_latest_results() -> list[Path]:
    """Find the latest result file for each dataset."""
    if not RESULTS_DIR.exists():
        return []

    # Group by dataset prefix, take latest
    by_dataset: dict[str, Path] = {}
    for path in sorted(RESULTS_DIR.glob("*.json")):
        # Filename: dataset_YYYYMMDD_HHMMSS.json
        parts = path.stem.rsplit("_", 2)
        if len(parts) >= 3:
            dataset = parts[0]
            if dataset not in by_dataset or path.stat().st_mtime > by_dataset[dataset].stat().st_mtime:
                by_dataset[dataset] = path

    return list(by_dataset.values())


def generate_report(result_files: list[Path]) -> str:
    """Generate a markdown report from result files."""
    lines = ["# Claude Agent Eval Report\n"]

    total_passed = 0
    total_failed = 0
    total_errors = 0
    total_cost = 0.0

    for path in result_files:
        with open(path) as f:
            data = json.load(f)

        dataset = data["dataset"]
        timestamp = data["timestamp"]
        passed = data["passed"]
        failed = data["failed"]
        errors = data["errors"]
        cost = data.get("total_cost_usd", 0)

        total_passed += passed
        total_failed += failed
        total_errors += errors
        total_cost += cost

        lines.append(f"## Dataset: {dataset}")
        lines.append(f"Run: {timestamp}")
        lines.append(f"Results: {passed} passed, {failed} failed, {errors} errors")
        lines.append(f"Cost: ${cost:.4f}\n")

        # Per-case results
        lines.append("| Case | Tool Selection | Contains | Overall |")
        lines.append("|------|---------------|----------|---------|")

        for case in data.get("cases", []):
            case_id = case["id"]
            scores = case.get("scores", {})
            tool_sel = scores.get("tool_selection", 0)
            contains = scores.get("response_contains", 0)
            overall = scores.get("overall", 0)
            status = "PASS" if overall >= 0.5 else "FAIL"
            lines.append(
                f"| {case_id} | {tool_sel:.2f} | {contains:.2f} | {overall:.2f} ({status}) |"
            )

        lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append(f"- Total passed: {total_passed}")
    lines.append(f"- Total failed: {total_failed}")
    lines.append(f"- Total errors: {total_errors}")
    lines.append(f"- Total cost: ${total_cost:.4f}")

    return "\n".join(lines)


def main():
    """CLI entry point."""
    result_files = find_latest_results()
    if not result_files:
        print("No eval results found. Run `make claude-agent-eval` first.")
        sys.exit(0)

    report = generate_report(result_files)
    print(report)

    # Also save to file
    report_path = RESULTS_DIR / "latest_report.md"
    report_path.write_text(report)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
