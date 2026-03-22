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

    by_dataset: dict[str, Path] = {}
    for path in sorted(RESULTS_DIR.glob("*.json")):
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

    # Error breakdown
    error_types: dict[str, int] = {}

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

        # Build header dynamically based on available scores
        has_quality = any(
            "response_quality" in c.get("scores", {})
            for c in data.get("cases", [])
        )
        has_context = any(
            "context_retention" in c.get("scores", {})
            for c in data.get("cases", [])
        )

        header = "| Case | Tools | Contains | "
        separator = "|------|-------|----------|"
        if has_quality:
            header += "Quality | "
            separator += "---------|"
        if has_context:
            header += "Context | "
            separator += "---------|"
        header += "Latency | Cost | Overall |"
        separator += "---------|------|---------|"

        lines.append(header)
        lines.append(separator)

        for case in data.get("cases", []):
            case_id = case["id"]
            scores = case.get("scores", {})
            error = case.get("error")

            if error:
                # Categorized error
                if isinstance(error, dict):
                    err_type = error.get("type", "unknown")
                    error_types[err_type] = error_types.get(err_type, 0) + 1
                    row = f"| {case_id} | ERROR ({err_type}) |"
                else:
                    error_types["unknown"] = error_types.get("unknown", 0) + 1
                    row = f"| {case_id} | ERROR |"
                # Pad remaining columns
                col_count = 5 + int(has_quality) + int(has_context)
                row += " |" * col_count
                lines.append(row)
                continue

            tool_sel = scores.get("tool_selection", 0)
            contains = scores.get("response_contains", 0)
            latency = scores.get("latency_ms", 0)
            cost_usd = scores.get("cost_usd", 0)
            overall = scores.get("overall", 0)
            status = "PASS" if overall >= 0.5 else "FAIL"

            row = f"| {case_id} | {tool_sel:.2f} | {contains:.2f} | "
            if has_quality:
                quality = scores.get("response_quality", -1)
                row += f"{quality:.2f} | " if quality >= 0 else "— | "
            if has_context:
                context = scores.get("context_retention", -1)
                row += f"{context:.2f} | " if context >= 0 else "— | "

            latency_str = f"{latency / 1000:.1f}s" if latency else "—"
            cost_str = f"${cost_usd:.3f}" if cost_usd else "—"
            row += f"{latency_str} | {cost_str} | {overall:.2f} ({status}) |"
            lines.append(row)

        lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append(f"- Total passed: {total_passed}")
    lines.append(f"- Total failed: {total_failed}")
    lines.append(f"- Total errors: {total_errors}")
    lines.append(f"- Total cost: ${total_cost:.4f}")

    if error_types:
        lines.append("\n### Error Breakdown")
        for err_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
            lines.append(f"- {err_type}: {count}")

    return "\n".join(lines)


def main():
    """CLI entry point."""
    result_files = find_latest_results()
    if not result_files:
        print("No eval results found. Run `make claude-agent-eval` first.")
        sys.exit(0)

    report = generate_report(result_files)
    print(report)

    report_path = RESULTS_DIR / "latest_report.md"
    report_path.write_text(report)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
