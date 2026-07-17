import unittest
from pathlib import Path
from server.artifact_contracts import parse_correction
class ArtifactTests(unittest.TestCase):
 def test_parses_correction_fixture(self):
  p=Path(__file__).parent/"fixtures/contracts/transcription/correction-manifest-v1/valid.json"; self.assertEqual("correction-manifest-v1",parse_correction(p)["contract_version"])
if __name__=="__main__": unittest.main()
