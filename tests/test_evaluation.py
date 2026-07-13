import tempfile
import unittest
from pathlib import Path

from server.evaluation import EvidenceJudgment, ExperimentManifest, ExperimentStore, JudgedDataset, JudgedQuery, paired_bootstrap, promotion_decision, retrieval_metrics
from server.explanations import create_counterfactual
from server.state import ClusteringSettings, ReductionSettings


class EvaluationTests(unittest.TestCase):
    def test_hand_calculated_retrieval_metrics(self):
        query = JudgedQuery("query", "fact", True, [EvidenceJudgment("a", "span-a", 3), EvidenceJudgment("b", "span-b", 2), EvidenceJudgment("c", "span-c", 0)])
        metrics = retrieval_metrics(query, ["a", "c", "b"])
        self.assertEqual(metrics["recall@20"], 1.0)
        self.assertAlmostEqual(metrics["precision@10"], 2 / 3)
        self.assertEqual(metrics["mrr"], 1.0)

    def test_dataset_roundtrip_and_stale_identity(self):
        dataset = JudgedDataset("set", "corpus", [JudgedQuery("query", "fact", True, [EvidenceJudgment("old-id", "episode:0-10", 3)])])
        with tempfile.TemporaryDirectory(dir="C:\\temp\\codex") as tmp:
            path = Path(tmp) / "dataset.json"
            dataset.save(path)
            loaded = JudgedDataset.load(path)
        self.assertEqual(loaded.queries[0].judgments[0].source_span_id, "episode:0-10")

    def test_manifest_id_is_immutable_and_notes_are_external(self):
        manifest = ExperimentManifest("corpus", "collection", "index", {"top_k": 10}, {"embedding": "model"}, {"retrieval": 42}, {"retrieval_ms": 1.0})
        self.assertEqual(manifest.run_id, manifest.run_id)
        with tempfile.TemporaryDirectory(dir="C:\\temp\\codex") as tmp:
            store = ExperimentStore(Path(tmp))
            run_dir = store.save(manifest, {"aggregate": {}}, "first")
            immutable = (run_dir / "run.json").read_text(encoding="utf-8")
            store.update_notes(manifest.run_id, "second")
            self.assertEqual((run_dir / "run.json").read_text(encoding="utf-8"), immutable)

    def test_committed_json_constructs_temporary_chroma_collection(self):
        try:
            import chromadb
        except ImportError as exc:
            self.skipTest(f"chromadb is not installed: {exc}")
        import json
        fixture = json.loads(Path("benchmarks/fixtures/synthetic-corpus.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(dir="C:\\temp\\codex") as tmp:
            client = chromadb.PersistentClient(path=tmp)
            collection = client.create_collection("synthetic")
            collection.add(ids=[item["id"] for item in fixture["documents"]], documents=[item["text"] for item in fixture["documents"]], embeddings=[item["embedding"] for item in fixture["documents"]], metadatas=[item["metadata"] for item in fixture["documents"]])
            self.assertEqual(collection.count(), len(fixture["documents"]))
            client._system.stop()
            chromadb.api.client.SharedSystemClient.clear_system_cache()

    def test_bootstrap_is_reproducible_and_descriptive_for_small_sets(self):
        first = paired_bootstrap([0.1, 0.2], [0.2, 0.4], samples=100, seed=7)
        second = paired_bootstrap([0.1, 0.2], [0.2, 0.4], samples=100, seed=7)
        self.assertEqual(first, second)
        self.assertTrue(first["descriptive_only"])

    def test_promotion_guardrails(self):
        baseline = {"ndcg@10": 0.5, "recall@20": 0.7, "constraint_accuracy": 1.0, "median_latency_ms": 100, "false_primary_support": 0}
        candidate = {"ndcg@10": 0.6, "recall@20": 0.7, "constraint_accuracy": 1.0, "median_latency_ms": 120, "false_primary_support": 0}
        self.assertTrue(promotion_decision(baseline, candidate)["promote"])
        candidate["median_latency_ms"] = 130
        self.assertFalse(promotion_decision(baseline, candidate)["promote"])

    def test_projection_cluster_and_embedding_diagnostics(self):
        try:
            import numpy as np
            from server.diagnostics import cluster_stability, embedding_quality, neighbor_preservation, projection_diagnostics
        except ImportError as exc:
            self.skipTest(f"scientific dependencies are not installed: {exc}")
        rng = np.random.default_rng(42)
        values = np.vstack([rng.normal(0, 0.1, (20, 4)), rng.normal(2, 0.1, (20, 4))])
        self.assertAlmostEqual(neighbor_preservation(values, values, 5), 1.0)
        projection = projection_diagnostics(values, ReductionSettings(method="PCA"), seeds=[1, 2], k=5)
        self.assertIn("trustworthiness", projection)
        clusters = cluster_stability(values, ClusteringSettings(method="KMeans", kmeans_clusters=2), runs=3)
        self.assertGreaterEqual(clusters["agreement"], 0.0)
        quality = embedding_quality(values, [{"speaker": "Host"}] * len(values))
        self.assertIn("anisotropy", quality)

    def test_counterfactual_scope_and_lineage(self):
        child = create_counterfactual("parent", {"candidate_depth": 20, "reranker_enabled": False})
        self.assertEqual(child.parent_run_id, "parent")
        with self.assertRaises(ValueError):
            create_counterfactual("parent", {"embedding_model": "other"})


if __name__ == "__main__":
    unittest.main()
