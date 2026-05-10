from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans

from .state import ClusteringSettings


def cluster_embeddings(embeddings: np.ndarray, settings: ClusteringSettings) -> tuple[list[str], str]:
    if embeddings.size == 0:
        return [], "none"
    if embeddings.shape[0] < 2:
        return ["0"] * embeddings.shape[0], "single"

    if settings.method in {"Auto", "HDBSCAN"}:
        try:
            import hdbscan

            labels = hdbscan.HDBSCAN(
                min_cluster_size=max(2, settings.hdbscan_min_cluster_size),
                min_samples=max(1, settings.hdbscan_min_samples),
                metric="euclidean",
            ).fit_predict(embeddings)
            return [str(label) for label in labels], "HDBSCAN"
        except Exception:
            if settings.method == "HDBSCAN":
                raise

    k = min(max(2, settings.kmeans_clusters), embeddings.shape[0])
    labels = KMeans(n_clusters=k, n_init="auto", random_state=settings.random_state).fit_predict(embeddings)
    return [str(label) for label in labels], "KMeans"


def nearest_neighbors(embeddings: np.ndarray, row_index: int, top_k: int = 8) -> list[int]:
    if embeddings.size == 0 or row_index < 0 or row_index >= len(embeddings):
        return []
    vectors = embeddings.astype(float)
    target = vectors[row_index]
    distances = np.linalg.norm(vectors - target, axis=1)
    order = np.argsort(distances)
    return [int(index) for index in order[1 : top_k + 1]]
