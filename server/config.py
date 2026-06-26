from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any


CACHE_VERSION = "analysis-topic-filter-v4"
DEFAULT_SEMANTIC_EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
NOISY_ANALYSIS_FIELDS = {
    "id",
    "row_index",
    "parent_id",
    "node_id",
    "chunk_id",
    "document_id",
    "source_id",
    "start_time",
    "end_time",
    "start",
    "end",
    "duration",
    "segment_count",
    "child_ids",
    "speaker_scope",
    "source",
    "source_file",
    "source_type",
    "title",
    "episode_title",
    "level",
    "node_type",
    "timestamp",
    "created_at",
    "updated_at",
    "episode_date",
    "episode_sort_key",
    "date",
    "year",
    "month",
    "day",
    "speaker",
    "speakers",
    "host",
    "guest",
}

CACHE_DIR = Path(".cache")
PROJECTION_CACHE_DIR = CACHE_DIR / "projections"
DATASET_RESPONSE_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
DATASET_RESPONSE_CACHE_LIMIT = 8
