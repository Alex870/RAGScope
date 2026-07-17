from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from server.evaluation import (
    EpisodeReference,
    EvaluationPack,
    EvidenceJudgment,
    JudgedDataset,
    JudgedQuery,
    NormalizedRunIdentity,
)


class Stage2EvaluationPackTests(unittest.TestCase):
    def test_pack_roundtrip_and_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "episode.wav"; audio.write_bytes(b"generated-audio-fixture")
            transcript = root / "episode.json"; transcript.write_text('{"segments": []}', encoding="utf-8")
            episode = EpisodeReference(
                "ep-1", audio.name, hashlib.sha256(audio.read_bytes()).hexdigest(),
                transcript.name, hashlib.sha256(transcript.read_bytes()).hexdigest(),
                audio_ranges=[{"start": 0.0, "end": 1.0}], speakers=["HOST"], speaker_aliases={"HOST": ["Host"]},
                glossary=["RAG"], protected_terms=["RAGScope"], conditions=["clean"], duration_seconds=60.0,
            )
            query = JudgedQuery(
                "What was said?", "fact", True, [EvidenceJudgment("doc-1", "span-1", 3, reviewer="reviewer")],
                acceptable_evidence_sets=[["doc-1"]], reference_claims=["A supported claim"],
                human_reviewed=True, adjudication_state="accepted",
            )
            pack = EvaluationPack("pack-1", JudgedDataset("pack", "corpus", [query]), [episode], reviewer="reviewer")
            path = root / "pack.json"; pack.save(path)
            loaded = EvaluationPack.load(path)
            report = loaded.validate(root, available_document_ids=["doc-1"], available_source_span_ids=["span-1"])
            self.assertTrue(report["valid"])
            self.assertEqual(report["readiness"], {"transcription": True, "retrieval": True, "answer": True})
            self.assertEqual({"HOST": ["Host"]}, loaded.episodes[0].speaker_aliases)
            self.assertEqual(["RAGScope"], loaded.episodes[0].protected_terms)
            self.assertEqual(60.0, loaded.episodes[0].duration_seconds)
            self.assertEqual(pack.fingerprint, loaded.fingerprint)

    def test_validator_reports_missing_changed_stale_and_incomplete_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "episode.wav"; source.write_bytes(b"changed")
            query = JudgedQuery("q", "fact", True, [EvidenceJudgment("old-doc", "old-span", 3)], human_reviewed=False, adjudication_state="pending")
            pack = EvaluationPack("pack", JudgedDataset("pack", "corpus", [query]), [EpisodeReference("ep", source.name, "0" * 64, "missing.json", "")])
            before = source.read_bytes()
            report = pack.validate(root, available_document_ids=["new-doc"], available_source_span_ids=["new-span"])
            self.assertFalse(report["valid"])
            self.assertTrue(any("hash changed" in item for item in report["errors"]))
            self.assertTrue(any("path is missing" in item for item in report["errors"]))
            self.assertTrue(any("Stale evidence IDs" in item for item in report["errors"]))
            self.assertEqual(report["incomplete_query_ids"], [query.query_id])
            self.assertEqual(source.read_bytes(), before)

    def test_normalized_run_identity_changes_only_with_immutable_evidence(self) -> None:
        values = dict(
            schema_version="1.0", corpus_fingerprint="corpus", evaluation_pack_fingerprint="pack",
            source_commits={"rag": "abc"}, model_identities={"embedding": "model"},
            config_fingerprints={"retrieval": "cfg"}, hardware_runtime={"python": "3.13"},
            started_at="2026-01-01T00:00:00Z", ended_at="2026-01-01T00:00:01Z", duration_seconds=1.0,
            raw_outcomes=[{"query_id": "q", "ranked_ids": ["doc"]}], aggregate_metrics={"mrr": 1.0},
        )
        first = NormalizedRunIdentity(**values)
        second = NormalizedRunIdentity(**{**values, "source_commits": {"rag": "def"}})
        self.assertNotEqual(first.run_id, second.run_id)


if __name__ == "__main__":
    unittest.main()
