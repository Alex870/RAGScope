"""Production parsers for producer-owned ecosystem fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


APPROVED_CORRECTION_STATES = {"approved", "accepted"}
MUTABLE_IDENTITY_KEYS = {"notes", "display_label", "display_labels", "ui_state"}


class ArtifactContractError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _correction_state(correction: Mapping[str, Any]) -> str:
    return str(correction.get("status") or correction.get("adjudication_state") or "accepted")


def _validate_v2_identity(manifest: Mapping[str, Any]) -> None:
    identity = {
        key: value
        for key, value in manifest.items()
        if key not in MUTABLE_IDENTITY_KEYS and key != "correction_set_id"
    }
    expected = f"correction_{hashlib.sha256(_canonical(identity)).hexdigest()}"
    if manifest.get("correction_set_id") != expected:
        raise ArtifactContractError("correction-set identity mismatch")


def parse_correction(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ArtifactContractError("correction payload must be an object")
    manifest = value.get("manifest", value)
    if not isinstance(manifest, dict):
        raise ArtifactContractError("correction manifest must be an object")
    transcript = value.get("transcript")
    version = str(manifest.get("contract_version") or "")
    if version not in {"correction-manifest-v1", "correction-manifest-v2"}:
        raise ArtifactContractError("unsupported correction")
    if version == "correction-manifest-v2":
        _validate_v2_identity(manifest)
        corrections = manifest.get("corrections", [])
    else:
        corrections = manifest.get("accepted_corrections", [])
    if not isinstance(corrections, list):
        raise ArtifactContractError("corrections must be a list")
    approved = [
        dict(item)
        for item in corrections
        if isinstance(item, dict) and _correction_state(item) in APPROVED_CORRECTION_STATES
    ]
    if transcript is not None:
        if not isinstance(transcript, dict):
            raise ArtifactContractError("transcript must be an object")
        if hashlib.sha256(_canonical(transcript)).hexdigest() != manifest.get("source_transcript_hash"):
            raise ArtifactContractError("stale transcript hash")
        spans = {
            str(item.get("source_span_id", item.get("id", ""))): item
            for item in transcript.get("segments", [])
            if isinstance(item, dict)
        }
        for correction in approved:
            source_span_id = str(correction.get("source_span_id") or "")
            field = str(correction.get("field") or "")
            guard = correction.get("before_value_guard", correction.get("before"))
            if not source_span_id or not field or spans.get(source_span_id, {}).get(field) != guard:
                raise ArtifactContractError("before value mismatch")
    result = dict(manifest)
    result["accepted_corrections"] = approved
    result["normalized_contract_version"] = "correction-manifest-v2"
    result["stale_source_span_ids"] = sorted(
        {
            str(item.get("source_span_id") or "")
            for item in approved
            if item.get("source_span_id")
        }
    )
    episode_ids = {str(item) for item in manifest.get("affected_episode_ids", []) if item}
    if isinstance(transcript, dict) and transcript.get("episode_id"):
        episode_ids.add(str(transcript["episode_id"]))
    result["affected_episode_ids"] = sorted(episode_ids)
    return result


def parse_delta(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("contract_version") != "processed-delta-v1":
        raise ArtifactContractError("unsupported processed delta")
    if any(
        item not in value.get("reasons", {})
        for item in value.get("changed_document_ids", []) + value.get("removed_document_ids", [])
    ):
        raise ArtifactContractError("delta reason missing")
    return value


def parse_release(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("contract_version") != "corpus-release-v1":
        raise ArtifactContractError("unsupported corpus release")
    if not value.get("release_id"):
        raise ArtifactContractError("release identity missing")
    return value


def parse_feedback(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("contract_version") != "chat-feedback-v1":
        raise ArtifactContractError("unsupported feedback")
    if value.get("creates_relevance_judgment") is not False:
        raise ArtifactContractError("feedback cannot become an automatic judgment")
    return value


def discover_correction_notifications(project_root: str | Path) -> list[dict[str, Any]]:
    inbox = Path(project_root) / "state" / "transcription_corrections"
    results = []
    for path in sorted(inbox.glob("*.json")) if inbox.exists() else []:
        payload: dict[str, Any] = {}
        manifest = None
        stale_spans: list[str] = []
        status = "invalid"
        error = ""
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ArtifactContractError("notification must be an object")
            payload = loaded
            if payload.get("contract_version") != "correction-notification-v1":
                raise ArtifactContractError("unsupported correction notification")
            manifest_path_value = str(payload.get("correction_manifest_path") or "").strip()
            if not manifest_path_value:
                raise ArtifactContractError("correction manifest path is missing")
            manifest_path = Path(manifest_path_value)
            if manifest_path.exists():
                manifest = parse_correction(manifest_path)
                stale_spans = manifest.get("stale_source_span_ids") or []
                status = "stale_judgments_pending"
            else:
                stale_spans = [str(item) for item in payload.get("stale_source_span_ids", []) if item]
                status = "downstream_pending"
                error = "correction manifest is unavailable"
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            error = str(exc)
        results.append(
            {
                **payload,
                "notification_path": str(path),
                "status": status,
                "error": error,
                "manifest": manifest,
                "stale_source_span_ids": sorted(set(stale_spans)),
            }
        )
    return results
