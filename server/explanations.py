from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExplanationRecord:
    query_variant: str
    filters: dict[str, Any]
    candidate_pool: str
    raw_score: float | None = None
    normalized_score: float | None = None
    fusion_contribution: float | None = None
    reranker_score: float | None = None
    diversity_penalty: float | None = None
    hierarchy_path: list[str] = field(default_factory=list)


@dataclass
class CounterfactualRun:
    changes: dict[str, Any]
    parent_run_id: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))


ALLOWED_COUNTERFACTUAL_CHANGES = {
    "filters",
    "candidate_depth",
    "query_variants",
    "channels",
    "fusion",
    "reranker_enabled",
}


def create_counterfactual(parent_run_id: str, changes: dict[str, Any]) -> CounterfactualRun:
    unsupported = set(changes).difference(ALLOWED_COUNTERFACTUAL_CHANGES)
    if unsupported:
        raise ValueError(f"Counterfactual cannot change: {', '.join(sorted(unsupported))}")
    return CounterfactualRun(changes=changes, parent_run_id=parent_run_id)

