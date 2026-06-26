from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb
import numpy as np
import pandas as pd


def load_collection_frame(path: Path, collection_name: str, max_load_size: int) -> tuple[pd.DataFrame, np.ndarray | None]:
    """Load the Chroma collection into a dataframe that the UI can inspect and render."""
    collection = chromadb.PersistentClient(path=str(path)).get_collection(collection_name)
    count = collection.count()
    if count == 0:
        return pd.DataFrame(), None
    payload = collection.get(limit=min(count, max_load_size), include=["documents", "embeddings", "metadatas"])
    ids = [str(item) for item in payload.get("ids", [])]
    documents = payload.get("documents") or [""] * len(ids)
    metadatas = payload.get("metadatas") or [{} for _ in ids]
    embeddings_raw = payload.get("embeddings")
    embeddings = np.asarray(embeddings_raw, dtype=float) if embeddings_raw is not None else None
    rows: list[dict[str, Any]] = []
    for index, doc_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) and isinstance(metadatas[index], dict) else {}
        text = str(documents[index] if index < len(documents) else "")
        row: dict[str, Any] = {
            "row_index": index,
            "id": doc_id,
            "document": text,
            "preview": preview(text),
            "source": str(first_present(metadata, ["source", "source_file", "file", "path"])),
            "title": str(first_present(metadata, ["title", "episode_title", "document_title"])),
            "metadata": metadata,
        }
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                row[f"meta.{key}"] = value
        rows.append(row)
    return pd.DataFrame(rows), embeddings


def empty_dataset_response(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows": [],
        "topics": {},
        "cluster_color_map": {},
        "metadata_fields": [],
        "metrics": {"loaded": 0, "clusters": 0, "embedding_dim": None, "clusterer": None},
        "validation": validation,
    }


def topic_records(topics: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for cluster, payload in topics.items():
        records.append({"cluster": str(cluster), **payload})
    return sorted(records, key=lambda item: str(item.get("cluster", "")))


def dataframe_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.replace({np.nan: None}).to_json(orient="records"))


def metadata_fields(frame: pd.DataFrame) -> list[dict[str, str]]:
    fields = []
    for column in sorted([item for item in frame.columns if item.startswith("meta.")]):
        series = frame[column].dropna()
        kind = "categorical"
        if pd.api.types.is_numeric_dtype(series):
            kind = "numeric"
        elif is_date_like(series):
            kind = "date"
        fields.append({"name": column, "label": column.removeprefix("meta."), "kind": kind})
    return fields


def is_date_like(values: pd.Series) -> bool:
    if values.empty or pd.api.types.is_numeric_dtype(values):
        return False
    try:
        parsed = pd.to_datetime(values.astype(str).head(25), errors="coerce", format="mixed")
    except TypeError:
        parsed = pd.to_datetime(values.astype(str).head(25), errors="coerce")
    return bool(parsed.notna().mean() > 0.8)


def first_present(metadata: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = metadata.get(key)
        if value not in (None, ""):
            return value
    return ""


def preview(text: str, limit: int = 220) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "..."
