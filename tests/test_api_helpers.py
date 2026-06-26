import unittest
from importlib.util import find_spec


if find_spec("chromadb") and find_spec("fastapi"):
    from server.api import react_state_to_workspace
else:
    react_state_to_workspace = None


@unittest.skipUnless(react_state_to_workspace is not None, "backend dependencies are not installed in this environment")
class ApiHelperTests(unittest.TestCase):
    def test_react_state_to_workspace_normalizes_sidebar_preferences(self) -> None:
        payload = {
            "sidebar": {
                "reductionMethod": "PCA",
                "sampling": False,
                "maxLoad": 2500,
                "dimensions": 3,
                "clusteringMethod": "KMeans",
                "clusterCount": 12,
                "minClusterSize": 6,
                "colorMode": "source",
                "textSearch": "economy",
                "semanticSearch": "trade policy",
                "semanticTopK": 7,
                "popupDelay": 0.4,
                "hoverEnabled": False,
            },
            "selected_points": ["1", "2"],
            "plot_relayout": {"scene": {"camera": {"eye": {"x": 1, "y": 1, "z": 1}}}},
        }

        workspace = react_state_to_workspace(payload)

        self.assertEqual(workspace["chart_view"], "3D")
        self.assertEqual(workspace["reduction"]["method"], "PCA")
        self.assertFalse(workspace["reduction"]["use_sampling"])
        self.assertEqual(workspace["clustering"]["method"], "KMeans")
        self.assertEqual(workspace["semantic_search_query"], "trade policy")
        self.assertEqual(workspace["selected_ids"], ["1", "2"])
        self.assertEqual(workspace["plot_view"], payload["plot_relayout"])
        self.assertFalse(workspace["popups_enabled"])


if __name__ == "__main__":
    unittest.main()
