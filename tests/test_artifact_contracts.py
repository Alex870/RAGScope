import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from server.artifact_contracts import (
    ArtifactContractError,
    discover_correction_notifications,
    parse_correction,
    parse_delta,
    parse_feedback,
    parse_release,
)


FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def _write_payload(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _refresh_v2_identity(manifest: dict) -> None:
    identity = {
        key: value
        for key, value in manifest.items()
        if key not in {"notes", "display_label", "display_labels", "ui_state", "correction_set_id"}
    }
    canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["correction_set_id"] = f"correction_{hashlib.sha256(canonical).hexdigest()}"


class ArtifactContractTests(unittest.TestCase):
    def test_parses_existing_contract_fixtures(self):
        self.assertTrue(parse_correction(FIXTURES / "transcription/correction-manifest-v1/valid.json"))
        self.assertTrue(parse_delta(FIXTURES / "podcast-rag/processed-delta-v1/valid.json"))
        self.assertTrue(parse_release(FIXTURES / "chroma-import/corpus-release-v1/valid.json"))
        self.assertFalse(
            parse_feedback(FIXTURES / "podcast-chat/chat-feedback-v1/valid.json")["creates_relevance_judgment"]
        )

    def test_parses_v2_and_exposes_only_approved_stale_evidence(self):
        parsed = parse_correction(FIXTURES / "transcription/correction-manifest-v2/valid.json")
        self.assertEqual(len(parsed["accepted_corrections"]), 1)
        self.assertEqual(parsed["stale_source_span_ids"], ["span-001"])
        self.assertEqual(parsed["affected_episode_ids"], ["episode-synthetic-v2-001"])

    def test_rejects_stale_hash_before_conflict_and_identity_tampering(self):
        fixture = FIXTURES / "transcription/correction-manifest-v2/valid.json"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.json"
            payload = json.loads(fixture.read_text(encoding="utf-8"))
            payload["transcript"]["segments"][0]["text"] = "Changed outside correction flow."
            _write_payload(path, payload)
            with self.assertRaisesRegex(ArtifactContractError, "stale transcript hash"):
                parse_correction(path)

            payload = json.loads(fixture.read_text(encoding="utf-8"))
            payload["manifest"]["corrections"][0]["before_value_guard"] = "Wrong value"
            payload["manifest"]["accepted_corrections"][0]["before_value_guard"] = "Wrong value"
            _refresh_v2_identity(payload["manifest"])
            _write_payload(path, payload)
            with self.assertRaisesRegex(ArtifactContractError, "before value mismatch"):
                parse_correction(path)

            payload = json.loads(fixture.read_text(encoding="utf-8"))
            payload["manifest"]["correction_set_id"] = "correction_tampered"
            _write_payload(path, payload)
            with self.assertRaisesRegex(ArtifactContractError, "identity mismatch"):
                parse_correction(path)

    def test_notification_discovery_reports_stale_pending_and_invalid(self):
        fixture = FIXTURES / "transcription/correction-manifest-v2/valid.json"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inbox = root / "state" / "transcription_corrections"
            inbox.mkdir(parents=True)
            _write_payload(
                inbox / "ready.json",
                {
                    "contract_version": "correction-notification-v1",
                    "correction_manifest_path": str(fixture),
                },
            )
            _write_payload(
                inbox / "pending.json",
                {
                    "contract_version": "correction-notification-v1",
                    "correction_manifest_path": str(root / "missing.json"),
                    "stale_source_span_ids": ["span-001"],
                },
            )
            _write_payload(inbox / "invalid.json", {"contract_version": "unknown"})
            by_name = {Path(item["notification_path"]).name: item for item in discover_correction_notifications(root)}
            self.assertEqual(by_name["ready.json"]["status"], "stale_judgments_pending")
            self.assertEqual(by_name["ready.json"]["stale_source_span_ids"], ["span-001"])
            self.assertEqual(by_name["pending.json"]["status"], "downstream_pending")
            self.assertEqual(by_name["invalid.json"]["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
