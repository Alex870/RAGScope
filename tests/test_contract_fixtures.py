import hashlib
import json
import unittest
from pathlib import Path

from server.chroma_loader import inspect_provenance, load_import_manifest


class ContractFixtureTests(unittest.TestCase):
    def _verify(self, root):
        origin = json.loads((root / "origin.json").read_text(encoding="utf-8"))
        for name, expected in origin["files"].items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), expected)

    def test_chroma_fixture_manifest_and_provenance(self):
        root = Path(__file__).parent / "fixtures" / "contracts" / "chroma-import" / "2.0"
        self._verify(root)
        self.assertEqual("2.0", load_import_manifest(root)["manifest_version"])
        report = inspect_provenance(root, [{"id":"leaf_1","metadata":{"node_type":"leaf_chunk","speaker":"Host","episode_date":"2026-01-01","source_segment_ids":["episode-1:segment:0"]}}])
        self.assertTrue(report["readable"])

    def test_chat_trace_fixture(self):
        root = Path(__file__).parent / "fixtures" / "contracts" / "podcast-chat" / "1.0"
        self._verify(root)
        trace = json.loads((root / "chat-trace.json").read_text(encoding="utf-8"))
        self.assertEqual("1.0", trace["trace_version"])
        self.assertTrue(trace["citations"][0]["source_segment_ids"])


if __name__ == "__main__":
    unittest.main()
