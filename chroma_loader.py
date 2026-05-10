from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import chromadb
import numpy as np
import pandas as pd
import streamlit as st


LOGGER = logging.getLogger(__name__)


@st.cache_resource(show_spinner=False)
def get_client(chroma_path: str) -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(Path(chroma_path).expanduser()))


@st.cache_data(show_spinner=False)
def list_collections(chroma_path: str) -> list[str]:
    client = get_client(chroma_path)
    names: list[str] = []
    for collection in client.list_collections():
        names.append(collection if isinstance(collection, str) else collection.name)
    return sorted(names)


@st.cache_data(show_spinner=True)
def load_collection(chroma_path: str, collection_name: str, max_load_size: int) -> tuple[pd.DataFrame, np.ndarray | None]:
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

