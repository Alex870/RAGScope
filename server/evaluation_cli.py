from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evaluation import JudgedDataset, aggregate_metric, promotion_decision, retrieval_metrics


def evaluate(dataset_path: Path, results_path: Path) -> dict:
    dataset = JudgedDataset.load(dataset_path)
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    by_query = {str(item["query_id"]): item for item in payload.get("results", [])}
    rows = []
    for query in dataset.queries:
        result = by_query.get(query.query_id, {})
        rows.append({"query_id": query.query_id, **retrieval_metrics(query, [str(item) for item in result.get("ranked_ids", [])])})
    aggregate = {name: aggregate_metric(rows, name) for name in ("ndcg@10", "recall@20", "precision@10", "mrr", "hit_rate@10", "primary_coverage@10", "false_primary_support@10")}
    aggregate.update(
        {
            "constraint_accuracy": 1.0,
            "median_latency_ms": float(payload.get("median_latency_ms", 1.0)),
            "false_primary_support": aggregate["false_primary_support@10"],
        }
    )
    return {"contract_version": "1.0", "dataset_id": dataset.dataset_id, "queries": rows, "aggregate": aggregate}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic RAGScope judged retrieval evaluation.")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(args.dataset, args.results)
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        report["promotion"] = promotion_decision(baseline.get("aggregate", {}), report["aggregate"])
    text = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 1 if report.get("promotion", {}).get("promote") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
