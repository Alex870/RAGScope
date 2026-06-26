from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Any

import numpy as np

from ..config import BGE_QUERY_PREFIX, DEFAULT_SEMANTIC_EMBEDDING_MODEL


def unique_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def semantic_search_candidate_ids(collection: Any, query_embedding: list[float], candidate_ids: list[str], top_k: int) -> list[str]:
    scored = score_candidate_documents(collection, query_embedding, candidate_ids, top_k, histogram_bins=10)
    return [item["id"] for item in scored["results"]]


def score_candidate_documents(
    collection: Any,
    query_embedding: list[float],
    candidate_ids: list[str],
    top_k: int,
    histogram_bins: int = 20,
) -> dict[str, Any]:
    include = ["embeddings", "documents", "metadatas"]
    payload = collection.get(ids=candidate_ids, include=include) if candidate_ids else collection.get(include=include)
    ids = [str(item) for item in payload.get("ids", [])]
    embeddings_raw = payload.get("embeddings")
    if not ids or embeddings_raw is None:
        return {"ids": [], "results": [], "histogram": [], "scores": [], "candidate_count": 0}
    vectors = np.asarray(embeddings_raw, dtype=float)
    query = np.asarray(query_embedding, dtype=float)
    if vectors.ndim != 2 or query.ndim != 1 or vectors.shape[1] != query.shape[0]:
        raise ValueError(
            f"Semantic candidate search dimension mismatch. "
            f"Candidates have {vectors.shape[1] if vectors.ndim == 2 else 'unknown'} dimensions, "
            f"query has {query.shape[0]}."
        )
    vector_norms = np.linalg.norm(vectors, axis=1)
    query_norm = np.linalg.norm(query)
    denominator = np.maximum(vector_norms * query_norm, 1e-12)
    scores = vectors.dot(query) / denominator
    order = np.argsort(scores)[::-1]
    top_order = order[: max(1, top_k)]
    documents = payload.get("documents") or []
    metadatas = payload.get("metadatas") or []
    results: list[dict[str, Any]] = []
    for rank, index in enumerate(top_order, start=1):
        row_id = ids[int(index)]
        metadata = metadatas[int(index)] if int(index) < len(metadatas) and isinstance(metadatas[int(index)], dict) else {}
        document = documents[int(index)] if int(index) < len(documents) else ""
        results.append(
            {
                "id": row_id,
                "rank": rank,
                "score": round(float(scores[int(index)]), 6),
                "preview": str(document or "")[:280],
                "metadata": metadata,
                "source": metadata.get("source") or metadata.get("source_file") or "",
                "title": metadata.get("title") or metadata.get("episode_title") or "",
                "level": metadata.get("level") or metadata.get("node_type") or "",
            }
        )
    return {
        "ids": [item["id"] for item in results],
        "results": results,
        "histogram": score_histogram(scores, histogram_bins),
        "scores": [round(float(score), 6) for score in scores.tolist()],
        "candidate_count": len(ids),
    }


def score_histogram(scores: np.ndarray, bins: int) -> list[dict[str, Any]]:
    if scores.size == 0:
        return []
    if float(np.min(scores)) == float(np.max(scores)):
        return [{"start": round(float(scores[0]), 6), "end": round(float(scores[0]), 6), "count": int(scores.size)}]
    counts, edges = np.histogram(scores, bins=bins)
    return [
        {
            "start": round(float(edges[index]), 6),
            "end": round(float(edges[index + 1]), 6),
            "count": int(count),
        }
        for index, count in enumerate(counts)
    ]


@lru_cache(maxsize=2)
def get_semantic_embedding_model(model_name: str = DEFAULT_SEMANTIC_EMBEDDING_MODEL):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Semantic search requires sentence-transformers. "
            "Run the launcher or install requirements.txt to add it."
        ) from exc
    return SentenceTransformer(model_name)


def embed_semantic_query(query: str) -> list[float]:
    model = get_semantic_embedding_model()
    encoded = model.encode(
        [f"{BGE_QUERY_PREFIX}{query.strip()}"],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    vector = np.asarray(encoded[0], dtype=float)
    return vector.tolist()


def collection_embedding_dim(collection: Any) -> int | None:
    try:
        sample = collection.get(limit=1, include=["embeddings"])
    except Exception:
        return None
    embeddings = sample.get("embeddings")
    if embeddings is None or len(embeddings) == 0:
        return None
    vector = np.asarray(embeddings[0], dtype=float)
    if vector.ndim == 0:
        return None
    return int(vector.shape[0])
