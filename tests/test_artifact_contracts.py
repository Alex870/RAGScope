import unittest
from pathlib import Path
from server.artifact_contracts import parse_correction,parse_delta,parse_release,parse_feedback
class ArtifactTests(unittest.TestCase):
 def test_parses_correction_fixture(self):
  p=Path(__file__).parent/"fixtures/contracts/transcription/correction-manifest-v1/valid.json"; self.assertEqual("correction-manifest-v1",parse_correction(p)["contract_version"])
 def test_parses_delta_fixture(self):
  p=Path(__file__).parent/"fixtures/contracts/podcast-rag/processed-delta-v1/valid.json"; self.assertEqual("processed-delta-v1",parse_delta(p)["contract_version"])
 def test_parses_release_fixture(self):
  p=Path(__file__).parent/"fixtures/contracts/chroma-import/corpus-release-v1/valid.json"; self.assertTrue(parse_release(p)["release_id"].startswith("release_"))
 def test_parses_feedback_as_adjudication_seed(self):
  p=Path(__file__).parent/"fixtures/contracts/podcast-chat/chat-feedback-v1/valid.json"; self.assertFalse(parse_feedback(p)["creates_relevance_judgment"])
if __name__=="__main__": unittest.main()
