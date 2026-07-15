from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from server.chroma_loader import inspect_provenance, trace_provenance
from server.evaluation import (
    EVALUATION_PACK_VERSION,
    EvidenceJudgment,
    ExperimentManifest,
    ExperimentStore,
    IncompatibleComparisonError,
    JudgedDataset,
    JudgedQuery,
    compare_reports,
    create_queries_from_documents,
    evaluate,
    evaluate_results,
    grade_ranked_candidates,
    render_comparison_markdown,
)


ROOT = Path(__file__).resolve().parents[1]


class Stage6AuthorityTests(unittest.TestCase):
    def test_evaluation_pack_roundtrip_preserves_provenance_adjudication_and_sets(self) -> None:
        dataset = JudgedDataset(
            "pack",
            "corpus-v1",
            [JudgedQuery(
                "Which passage supports the claim?", "fact", True,
                [EvidenceJudgment("doc-a", "span-a", 3)],
                acceptable_evidence_sets=[["doc-a"], ["doc-b"]],
                provenance="generated", human_reviewed=False,
                adjudication_state="pending",
            )],
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pack.json"
            dataset.save_pack(path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["format"], EVALUATION_PACK_VERSION)
            loaded = JudgedDataset.load(path)
        self.assertEqual(loaded.queries[0].provenance, "generated")
        self.assertEqual(loaded.queries[0].adjudication_state, "pending")
        self.assertEqual(loaded.queries[0].acceptable_evidence_sets, [["doc-a"], ["doc-b"]])
        self.assertEqual(dataset.fingerprint, loaded.fingerprint)

    def test_selected_documents_create_unjudged_review_seeds(self) -> None:
        queries = create_queries_from_documents([{"id": "doc-a", "metadata": {"speaker": "Host", "episode_date": "2026-01-01", "node_type": "leaf_chunk"}}], ["Review this passage"], provenance="human")
        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0].query, "Review this passage")
        self.assertEqual(queries[0].adjudication_state, "pending")
        self.assertEqual(queries[0].judgments[0].grade, 3)

    def test_synthetic_fixture_metrics_and_per_query_rankings(self) -> None:
        report = evaluate(ROOT / "benchmarks/fixtures/synthetic-dataset.json", ROOT / "benchmarks/fixtures/synthetic-results.json")
        self.assertEqual(report["aggregate"]["ndcg@10"], 0.5)
        self.assertEqual(report["aggregate"]["constraint_accuracy"], 1.0)
        self.assertEqual(report["aggregate"]["no_answer_false_positive_rate"], 0.0)
        self.assertEqual(report["queries"][0]["ranked_ids"][0], "leaf-ai")
        self.assertEqual(report["queries"][0]["ranked_results"][0]["grade"], 3)
        self.assertTrue(report["judged_dataset_fingerprint"])

    def test_degraded_candidate_fails_named_query_guardrail(self) -> None:
        baseline = evaluate(ROOT / "benchmarks/fixtures/synthetic-dataset.json", ROOT / "benchmarks/fixtures/synthetic-results.json")
        degraded = evaluate(ROOT / "benchmarks/fixtures/synthetic-dataset.json", ROOT / "benchmarks/fixtures/synthetic-degraded-results.json")
        comparison = compare_reports(baseline, degraded, samples=100, seed=17)
        self.assertFalse(comparison["promotion"]["promote"])
        self.assertIn("nDCG@10 regressed", comparison["promotion"]["failures"])
        self.assertIn("q1", [row["query_id"] for row in comparison["worst_regressions"]])
        self.assertIn("RAGScope Evaluation Comparison", render_comparison_markdown(comparison))

    def test_comparison_rejects_mismatched_fingerprints_and_query_sets(self) -> None:
        baseline = {"corpus_fingerprint": "a", "judged_dataset_fingerprint": "j", "queries": [{"query_id": "q1", "ndcg@10": 1.0}], "aggregate": {}}
        with self.assertRaises(IncompatibleComparisonError):
            compare_reports(baseline, {**baseline, "corpus_fingerprint": "b"})
        with self.assertRaises(IncompatibleComparisonError):
            compare_reports(baseline, {**baseline, "queries": []})

    def test_manifest_identity_includes_stage6_dimensions(self) -> None:
        first = ExperimentManifest("corpus", "collection", "index", {"top_k": 10}, {"embedding": "model"}, {"retrieval": 42}, {"retrieval_ms": 1.0}, judged_dataset_fingerprint="judged-a", representation_id="page-content-v1", embedding_dimension=4)
        second = ExperimentManifest("corpus", "collection", "index", {"top_k": 10}, {"embedding": "model"}, {"retrieval": 42}, {"retrieval_ms": 1.0}, judged_dataset_fingerprint="judged-b", representation_id="page-content-v1", embedding_dimension=4)
        self.assertNotEqual(first.run_id, second.run_id)
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(Path(tmp))
            store.save(first, {"queries": [{"query_id": "q1", "ranked_ids": ["doc"]}]})
            with self.assertRaises(FileExistsError):
                store.save(first, {"queries": [{"query_id": "q1", "ranked_ids": ["different"]}]})

    def test_provenance_inspector_separates_incomplete_from_hard_violations(self) -> None:
        fixture = ROOT.parent / "Chroma DB Import" / "tests" / "fixtures" / "golden_export"
        rows = [{"id": "node-001", "metadata": {"node_type": "leaf_chunk", "speaker": "Host", "episode_date": "2026-01-01", "source_segment_ids": ["episode:0-10"]}}]
        report = inspect_provenance(fixture, rows)
        self.assertTrue(report["readable"])
        self.assertEqual(report["representation_id"], "golden-representation-v1")
        self.assertEqual(report["embedding"]["dimension"], 4)
        self.assertEqual(report["hierarchy_closure"]["transcript_links"]["node-001"], ["episode:0-10"])
        trace = trace_provenance("node-001", rows)
        self.assertTrue(trace["complete"])
        bad = inspect_provenance(fixture, [{"metadata": {"node_type": "leaf_chunk"}}])
        self.assertFalse(bad["readable"])
        self.assertTrue(bad["hard_violations"])

    def test_ranked_candidate_grading_marks_hard_negatives_and_acceptable_sets(self) -> None:
        query = JudgedQuery("q", "fact", True, [EvidenceJudgment("a", "span", 3)], acceptable_evidence_sets=[["a"], ["b"]], hard_negative_ids=["c"])
        graded = grade_ranked_candidates(query, ["c", "b"])
        self.assertTrue(graded[0]["hard_negative"])
        self.assertEqual(graded[1]["acceptable_set_hits"], [False, True])


if __name__ == "__main__":
    unittest.main()
