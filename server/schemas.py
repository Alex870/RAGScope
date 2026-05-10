from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from state import ClusteringSettings, ReductionSettings


class CollectionRequest(BaseModel):
    chroma_path: str = "./chroma"


class BrowseFolderRequest(BaseModel):
    start_path: str = "."


class DatasetRequest(BaseModel):
    chroma_path: str = "./chroma"
    collection_name: str = ""
    max_load_size: int = Field(default=10000, ge=1, le=250000)
    chart_view: str = "2D"
    reduction: ReductionSettings = Field(default_factory=ReductionSettings)
    clustering: ClusteringSettings = Field(default_factory=ClusteringSettings)


class SearchRequest(BaseModel):
    chroma_path: str
    collection_name: str = ""
    query: str
    top_k: int = Field(default=10, ge=1, le=200)
    candidate_ids: list[str] = Field(default_factory=list)


class RetrievalExperimentRequest(SearchRequest):
    mode: str = "Current filtered set"
    histogram_bins: int = Field(default=20, ge=5, le=80)


class DocumentRequest(BaseModel):
    chroma_path: str
    collection_name: str = ""
    id: str


class AnalyzeSelectionRequest(DatasetRequest):
    selected_ids: list[str] = Field(default_factory=list, max_length=5000)


class SaveViewRequest(BaseModel):
    name: str = "Untitled View"
    description: str = ""
    state: dict[str, Any]


class RenameViewRequest(BaseModel):
    name: str


class LlmProviderConfig(BaseModel):
    provider: str = "Disabled"
    base_url: str = "http://127.0.0.1:1234/v1"
    model: str = ""
    api_key: str = ""


class LlmModelsRequest(BaseModel):
    provider: LlmProviderConfig


class LlmQueryGenerationRequest(BaseModel):
    provider: LlmProviderConfig
    collection_name: str = ""
    sample_chunks: list[dict[str, Any]] = Field(default_factory=list)
    existing_queries: list[str] = Field(default_factory=list)
    query_count: int = Field(default=8, ge=1, le=20)


class LlmAuditInterpretRequest(BaseModel):
    provider: LlmProviderConfig
    audit_report: dict[str, Any]
    contexts: list[dict[str, Any]] = Field(default_factory=list)
    limit_context: bool = False
