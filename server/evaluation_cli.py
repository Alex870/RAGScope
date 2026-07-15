from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evaluation import compare_reports, evaluate as evaluate_report, render_comparison_markdown


def evaluate(dataset_path: Path, results_path: Path) -> dict:
    return evaluate_report(dataset_path, results_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic RAGScope judged retrieval evaluation.")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compare", type=Path, help="Compare the evaluated report with a baseline report")
    parser.add_argument("--markdown", type=Path, help="Write a Markdown promotion report when comparing")
    args = parser.parse_args()
    report = evaluate(args.dataset, args.results)
    baseline_path = args.compare or args.baseline
    if baseline_path:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        comparison = compare_reports(baseline, report)
        report["comparison"] = comparison
        report["promotion"] = comparison["promotion"]
        if args.markdown:
            args.markdown.parent.mkdir(parents=True, exist_ok=True)
            args.markdown.write_text(render_comparison_markdown(comparison), encoding="utf-8")
    text = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 1 if report.get("promotion", {}).get("promote") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
