from __future__ import annotations

import json
import pickle
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..clustering import cluster_embeddings
from ..config import CACHE_VERSION, DATASET_RESPONSE_CACHE, DATASET_RESPONSE_CACHE_LIMIT, PROJECTION_CACHE_DIR
from ..reducers import reduce_embeddings
from ..schemas import DatasetRequest
from ..topics import label_topics


def dataset_cache_key(path: Path, request: DatasetRequest, signature: dict[str, Any]) -> str:
    payload = {
        "signature": signature,
        "cache_version": CACHE_VERSION,
        "max_load_size": request.max_load_size,
        "chart_view": request.chart_view,
        "reduction": asdict(request.reduction),
        "clustering": asdict(request.clustering),
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def memory_cache_get(key: str) -> dict[str, Any] | None:
    cached = DATASET_RESPONSE_CACHE.get(key)
    if cached is None:
        return None
    DATASET_RESPONSE_CACHE.move_to_end(key)
    response = deepcopy(cached)
    response["cache"] = {**response.get("cache", {}), "memory": True}
    return response


def memory_cache_set(key: str, response: dict[str, Any]) -> None:
    DATASET_RESPONSE_CACHE[key] = deepcopy(response)
    DATASET_RESPONSE_CACHE.move_to_end(key)
    while len(DATASET_RESPONSE_CACHE) > DATASET_RESPONSE_CACHE_LIMIT:
        DATASET_RESPONSE_CACHE.popitem(last=False)


def projection_cache_path(key: str) -> Path:
    PROJECTION_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return PROJECTION_CACHE_DIR / f"{key}.pickle"


def load_or_compute_projection(
    key: str,
    frame: pd.DataFrame,
    embeddings: np.ndarray,
    request: DatasetRequest,
    dimensions: int,
) -> dict[str, Any]:
    """Reuse expensive projection and clustering work when the collection and view settings match."""
    path = projection_cache_path(key)
    if path.exists():
        try:
            with path.open("rb") as handle:
                return pickle.load(handle)
        except Exception:
            path.unlink(missing_ok=True)

    coords = reduce_embeddings(embeddings, request.reduction, dimensions)
    labels, clusterer = cluster_embeddings(embeddings, request.clustering)
    labeled_frame = frame.copy()
    labeled_frame["cluster"] = labels
    labeled_frame, topics = label_topics(labeled_frame, embeddings)
    payload = {
        "coords": coords,
        "labels": labels,
        "clusterer": clusterer,
        "topic_labels": labeled_frame["topic_label"].tolist(),
        "topics": topics,
    }
    try:
        with path.open("wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass
    return payload
