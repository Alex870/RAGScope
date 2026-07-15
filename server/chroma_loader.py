from __future__ import annotations

import logging
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    import chromadb
except ImportError:  # Provenance inspection remains usable without the optional Chroma client.
    chromadb = None  # type: ignore[assignment]
try:
    import numpy as np
except ImportError:  # Optional for manifest-only audit workflows.
    np = None  # type: ignore[assignment]
try:
    import pandas as pd
except ImportError:  # Optional for manifest-only audit workflows.
    pd = None  # type: ignore[assignment]


LOGGER = logging.getLogger(__name__)
SUPPORTED_IMPORT_MANIFEST_MAJOR = 2


def load_import_manifest(chroma_path: str | Path) -> dict[str, Any]:
    """Load the importer manifest without opening Chroma; missing files stay inspectable."""
    root = Path(chroma_path).expanduser()
    manifest_path = root / "import_manifest.json"
    if not manifest_path.exists():
        return {"available": False, "path": str(manifest_path), "reason": "import_manifest.json is missing"}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["available"] = True
        payload["path"] = str(manifest_path)
        payload["content_fingerprint"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        return payload
    except (OSError, json.JSONDecodeError) as exc:
        return {"available": False, "path": str(manifest_path), "reason": f"{type(exc).__name__}: {exc}"}


def inspect_provenance(chroma_path: str | Path, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Validate import-level identity and row-level evidence closure for audit reports."""
    root = Path(chroma_path).expanduser()
    manifest = load_import_manifest(root)
    hard_violations: list[str] = []
    incomplete: list[str] = []
    if manifest.get("available"):
        try:
            version = int(str(manifest.get("manifest_version", "0.0")).split(".", 1)[0])
            if version > SUPPORTED_IMPORT_MANIFEST_MAJOR:
                hard_violations.append(f"Unsupported import manifest major version: {manifest.get('manifest_version')}")
        except ValueError:
            hard_violations.append("Import manifest version is invalid")
        if isinstance(manifest.get("validation"), dict) and manifest["validation"].get("valid") is False:
            hard_violations.append("Import manifest validation is not valid")
    else:
        incomplete.append(str(manifest.get("reason") or "Import manifest is unavailable"))
    podcast_path = root / "podcast.json"
    podcast: dict[str, Any] = {}
    if podcast_path.exists():
        try:
            podcast = json.loads(podcast_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            hard_violations.append(f"podcast.json is unreadable: {exc}")
    else:
        incomplete.append("podcast.json is missing")
    rows = rows or []
    required = ("id", "node_type", "speaker", "episode_date")
    completeness = {field: sum(bool((row.get("metadata") or {}).get(field) or row.get(field)) for row in rows) / max(1, len(rows)) for field in required}
    missing_rows = [str(row.get("id") or "") for row in rows if not row.get("id")]
    if missing_rows:
        hard_violations.append(f"{len(missing_rows)} loaded rows have no stable ID")
    node_map = {str(row.get("id")): row for row in rows if row.get("id")}
    closure_missing: list[str] = []
    transcript_links: dict[str, list[str]] = {}
    for row_id, row in node_map.items():
        metadata = row.get("metadata") or row
        node_type = str(metadata.get("node_type") or metadata.get("level") or "")
        children = metadata.get("child_ids") or metadata.get("children") or []
        if isinstance(children, str):
            children = [children]
        if node_type not in {"leaf_chunk", "leaf", "transcript_segment", ""} and not children:
            closure_missing.append(row_id)
        evidence = metadata.get("source_segment_ids") or metadata.get("source_spans") or metadata.get("primary_evidence_ids") or []
        if isinstance(evidence, str):
            evidence = [evidence]
        if evidence:
            transcript_links[row_id] = [str(value) for value in evidence]
    if closure_missing:
        incomplete.append(f"{len(closure_missing)} derived nodes have no child evidence links")
    if not rows:
        incomplete.append("No loaded rows were supplied for row-level provenance checks")
    return {
        "readable": not hard_violations,
        "hard_violations": hard_violations,
        "incomplete_but_readable": incomplete,
        "manifest": manifest,
        "podcast": {"available": bool(podcast), "database_id": podcast.get("database_id"), "collection_name": podcast.get("collection_name")},
        "embedding": {"fingerprint": manifest.get("embedding_fingerprint") or manifest.get("embedding_cache", {}).get("fingerprint", ""), "model": manifest.get("embedding_model") or podcast.get("embedding_model"), "dimension": manifest.get("embedding_dimension") or podcast.get("embedding_dimension")},
        "representation_id": manifest.get("representation_id") or (manifest.get("representation") or {}).get("representation_id") or podcast.get("representation_id", ""),
        "selected_speakers": manifest.get("selected_speakers") or [],
        "source_cache_ids": [str(item.get("source_identity") or item.get("content_fingerprint") or item.get("path") or "") for item in manifest.get("source_files", []) if isinstance(item, dict)],
        "hierarchy_closure": {"checked_rows": len(rows), "missing_child_links": closure_missing, "transcript_links": transcript_links},
        "speaker_date_completeness": {"speaker": completeness["speaker"], "episode_date": completeness["episode_date"]},
        "metadata_completeness": completeness,
    }


def trace_provenance(document_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Trace a vector/document row through processed-node and transcript identifiers when present."""
    by_id = {str(row.get("id")): row for row in rows}
    visited: set[str] = set()
    transcript: list[str] = []
    processed: list[str] = []

    def visit(node_id: str) -> None:
        if not node_id or node_id in visited:
            return
        visited.add(node_id)
        row = by_id.get(node_id)
        if not row:
            return
        processed.append(node_id)
        metadata = row.get("metadata") or row
        values = metadata.get("source_segment_ids") or metadata.get("source_spans") or metadata.get("primary_evidence_ids") or []
        transcript.extend([str(value) for value in values] if isinstance(values, list) else [str(values)])
        children = metadata.get("child_ids") or metadata.get("children") or []
        if isinstance(children, str):
            children = [children]
        for child in children:
            visit(str(child))

    visit(str(document_id))
    return {"vector_id": str(document_id), "processed_node_ids": processed, "transcript_evidence_ids": sorted(set(transcript)), "complete": bool(processed and transcript), "missing": not bool(processed)}


def get_client(chroma_path: str) -> chromadb.PersistentClient:
    if chromadb is None:
        raise RuntimeError("chromadb is not installed; manifest/provenance inspection is still available")
    return chromadb.PersistentClient(path=str(Path(chroma_path).expanduser()))


def list_collections(chroma_path: str) -> list[str]:
    client = get_client(chroma_path)
    names: list[str] = []
    for collection in client.list_collections():
        names.append(collection if isinstance(collection, str) else collection.name)
    return sorted(names)


def load_collection(chroma_path: str, collection_name: str, max_load_size: int) -> tuple[pd.DataFrame, np.ndarray | None]:
    if np is None or pd is None:
        raise RuntimeError("numpy and pandas are required to load collection rows")
    client = get_client(chroma_path)
    collection = client.get_collection(collection_name)
    count = collection.count()
    if count == 0:
        return pd.DataFrame(), None

    limit = min(count, max_load_size)
    payload = collection.get(limit=limit, include=["documents", "embeddings", "metadatas"])
    ids = [str(item) for item in payload.get("ids", [])]
    documents = payload.get("documents") or [""] * len(ids)
    metadatas = payload.get("metadatas") or [{} for _ in ids]
    embeddings_raw = payload.get("embeddings")
    embeddings = np.asarray(embeddings_raw, dtype=float) if embeddings_raw is not None else None

    rows: list[dict[str, Any]] = []
    for index, doc_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) and isinstance(metadatas[index], dict) else {}
        text = str(documents[index] if index < len(documents) else "")
        source = first_present(metadata, ["source", "source_file", "file", "path"])
        title = first_present(metadata, ["title", "episode_title", "document_title"])
        row = {
            "id": doc_id,
            "document": text,
            "preview": preview(text),
            "source": str(source or ""),
            "title": str(title or ""),
            "metadata": metadata,
        }
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                row[f"meta.{key}"] = value
        rows.append(row)

    frame = pd.DataFrame(rows)
    return frame, embeddings


def semantic_search(chroma_path: str, collection_name: str, query: str, top_k: int) -> list[str]:
    if not query.strip():
        return []
    try:
        collection = get_client(chroma_path).get_collection(collection_name)
        result = collection.query(query_texts=[query], n_results=max(1, top_k))
    except Exception as exc:
        LOGGER.warning("Semantic search failed: %s", exc)
        return []
    ids = result.get("ids") or [[]]
    return [str(item) for item in ids[0]]


def first_present(metadata: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = metadata.get(key)
        if value not in (None, ""):
            return value
    return ""


def preview(text: str, limit: int = 220) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "..."

