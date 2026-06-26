import unittest

from server.state import WorkspaceState


class WorkspaceStateTests(unittest.TestCase):
    def test_from_dict_merges_nested_settings_without_unknown_fields(self) -> None:
        state = WorkspaceState.from_dict({
            "name": "Review View",
            "reduction": {"method": "PCA", "sample_size": 1200, "unknown": "ignored"},
            "clustering": {"method": "KMeans", "kmeans_clusters": 11, "noise": 9},
            "unexpected": "value",
        })

        self.assertEqual(state.name, "Review View")
        self.assertEqual(state.reduction.method, "PCA")
        self.assertEqual(state.reduction.sample_size, 1200)
        self.assertEqual(state.clustering.method, "KMeans")
        self.assertEqual(state.clustering.kmeans_clusters, 11)
        self.assertFalse(hasattr(state, "unexpected"))

    def test_to_dict_serializes_nested_dataclasses(self) -> None:
        state = WorkspaceState(name="Serialized View")

        payload = state.to_dict()

        self.assertEqual(payload["name"], "Serialized View")
        self.assertIn("reduction", payload)
        self.assertEqual(payload["reduction"]["method"], state.reduction.method)
        self.assertIn("clustering", payload)


if __name__ == "__main__":
    unittest.main()
