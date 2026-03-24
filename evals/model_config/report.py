"""Generate comparison report from model config eval results."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"


def find_latest_result() -> Path | None:
    if not RESULTS_DIR.exists():
        return None
    files = sorted(RESULTS_DIR.glob("sweep_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def generate_report(result_path: Path) -> str:
    with open(result_path) as f:
        results = json.load(f)

    lines = ["# Model Config Eval Report\n"]
    lines.append(f"Results: `{result_path.name}`\n")

    # Build header from all score dimensions
    all_dims = set()
    for r in results:
        all_dims.update(r.get("avg_scores", {}).keys())
    all_dims.discard("overall")
    dims = sorted(all_dims)

    header = f"| {'Config':<30} |"
    separator = f"|{'-'*31}|"
    for d in dims:
        header += f" {d[:12]:>12} |"
        separator += f"{'-'*14}|"
    header += f" {'Latency':>10} | {'Overall':>8} |"
    separator += f"{'-'*12}|{'-'*10}|"

    lines.append(header)
    lines.append(separator)

    for r in results:
        scores = r.get("avg_scores", {})
        row = f"| {r['config']['name']:<30} |"
        for d in dims:
            val = scores.get(d, 0)
            row += f" {val:>12.2f} |"
        row += f" {r['avg_duration_ms']:>8}ms | {scores.get('overall', 0):>7.2f} |"
        lines.append(row)

    lines.append("")
    lines.append("## Per-Config Details\n")
    for r in results:
        name = r["config"]["name"]
        lines.append(f"### {name}")
        lines.append(f"- Cases: {r['completed']}/{r['total_cases']} ({r['errors']} errors)")
        lines.append(f"- Avg latency: {r['avg_duration_ms']}ms")
        lines.append(f"- Avg scores: {json.dumps(r['avg_scores'], indent=2)}")
        lines.append("")

    return "\n".join(lines)


def main():
    result_path = find_latest_result()
    if not result_path:
        print("No results found. Run `make model-eval` first.")
        sys.exit(0)

    report = generate_report(result_path)
    print(report)

    report_path = RESULTS_DIR / "latest_report.md"
    report_path.write_text(report)
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
