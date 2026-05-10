from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ReductionSettings:
    method: str = "UMAP"
    n_neighbors: int = 15
    min_dist: float = 0.1
    metric: str = "cosine"
    pca_random_state: int = 42
    sample_size: int = 5000
    use_sampling: bool = False


@dataclass
class ClusteringSettings:
    method: str = "Auto"
    hdbscan_min_cluster_size: int = 8
    hdbscan_min_samples: int = 3
    kmeans_clusters: int = 8
    random_state: int = 42


@dataclass
class WorkspaceState:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled View"
    description: str = ""
    timestamp: str = field(default_factory=utc_now)
    chroma_path: str = "./chroma"
    collection_name: str = ""
    max_load_size: int = 10000
    reduction: ReductionSettings = field(default_factory=ReductionSettings)
    clustering: ClusteringSettings = field(default_factory=ClusteringSettings)
    chart_view: str = "2D"
    chart_interaction_mode: str = "Pan"
    popups_enabled: bool = True
    popup_delay_seconds: float = 1.0
    table_height: int = 280
    metadata_filters: dict[str, Any] = field(default_factory=dict)
    color_mode: str = "cluster"
    text_search_query: str = ""
    semantic_search_query: str = ""
    semantic_top_k: int = 10
    selected_ids: list[str] = field(default_factory=list)
    highlighted_ids: list[str] = field(default_factory=list)
    highlighted_neighbors: list[str] = field(default_factory=list)
    highlighted_clusters: list[str] = field(default_factory=list)
    visible_clusters: list[str] = field(default_factory=list)
    hidden_clusters: list[str] = field(default_factory=list)
    plot_view: dict[str, Any] = field(default_factory=dict)
    sidebar_settings: dict[str, Any] = field(default_factory=dict)
    table_state: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    restore_on_startup: bool = True

    def touch(self) -> None:
        self.timestamp = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkspaceState":
        data = dict(payload)
        reduction = data.get("reduction") or {}
        clustering = data.get("clustering") or {}
        data["reduction"] = ReductionSettings(**{
            **asdict(ReductionSettings()),
            **{k: v for k, v in reduction.items() if k in asdict(ReductionSettings())},
        })
        data["clustering"] = ClusteringSettings(**{
            **asdict(ClusteringSettings()),
            **{k: v for k, v in clustering.items() if k in asdict(ClusteringSettings())},
        })
        allowed = set(cls.__dataclass_fields__.keys())
        return cls(**{key: value for key, value in data.items() if key in allowed})
