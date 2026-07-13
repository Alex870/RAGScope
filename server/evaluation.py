from __future__ import annotations

import hashlib
import json
import math
import platform
import random
import statistics
import sys
import uuid
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATASET_VERSION = "1.0"
EXPERIMENT_VERSION = "1.0"
REPORT_VERSION = "1.0"
RELEVANCE = {0: "irrelevant", 1: "related", 2: "relevant_or_derived", 3: "primary_evidence"}


class ContractCompatibilityError(ValueError):
    pass


def require_compatible(encountered: str, supported: str, path: str | Path, component: str = "RAGScope") -> None:
    try:
        actual_major = int(str(encountered).split(".", 1)[0])
        supported_major = int(str(supported).split(".", 1)[0])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid contract version in {path}: {encountered!r}") from exc
    if actual_major > supported_major:
        raise ContractCompatibilityError(
            f"{component} cannot read {path}: encountered contract {encountered}; maximum supported "
            f"contract is {supported}. Upgrade {component}."
        )


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceJudgment:
    document_id: str
    source_span_id: str
    grade: int
    reviewer: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if self.grade not in RELEVANCE:
            raise ValueError("Evidence grade must be between 0 and 3")


@dataclass
class JudgedQuery:
    query: str
    query_class: str
    answerable: bool
    judgments: list[EvidenceJudgment]
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    expected_speakers: list[str] = field(default_factory=list)
    date_start: str = ""
    date_end: str = ""
    acceptable_evidence_sets: list[list[str]] = field(default_factory=list)
    reference_claims: list[str] = field(default_factory=list)
    hard_negative_ids: list[str] = field(default_factory=list)
    provenance: str = "human"
    human_reviewed: bool = True
    second_reviewer: str = ""
    adjudication_note: str = ""


@dataclass
class JudgedDataset:
    name: str
    corpus_fingerprint: str
    queries: list[JudgedQuery]
    dataset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    contract_version: str = DATASET_VERSION
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "JudgedDataset":
        payload = json.loads(path.read_text(encoding="utf-8"))
        require_compatible(payload.get("contract_version", "1.0"), DATASET_VERSION, path)
        queries = []
        for item in payload.get("queries", []):
            record = dict(item)
            judgments = [EvidenceJudgment(**value) for value in record.pop("judgments", [])]
            queries.append(JudgedQuery(judgments=judgments, **record))
        return cls(queries=queries, **{key: value for key, value in payload.items() if key != "queries"})


class ExperimentStore:
    """Persist immutable run data independently from mutable operator notes."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, manifest: ExperimentManifest, report: dict[str, Any], notes: str = "") -> Path:
        run_dir = self.root / manifest.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        immutable = run_dir / "run.json"
        payload = {"manifest": asdict(manifest), "run_id": manifest.run_id, "report": report}
        encoded = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
        if immutable.exists() and immutable.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"Immutable run {manifest.run_id} already exists with different data")
        immutable.write_text(encoded, encoding="utf-8")
        try:
            os.chmod(immutable, 0o444)
        except OSError:
            pass
        self.update_notes(manifest.run_id, notes)
        return run_dir

    def update_notes(self, run_id: str, notes: str) -> Path:
        path = self.root / run_id / "notes.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"notes": notes}, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        return path


@dataclass(frozen=True)
class ExperimentManifest:
    corpus_fingerprint: str
    collection_name: str
    index_identity: str
    retrieval_settings: dict[str, Any]
    model_settings: dict[str, Any]
    seeds: dict[str, int]
    timings: dict[str, float]
    code_version: str = "unknown"
    hardware: dict[str, str] = field(default_factory=lambda: {"platform": platform.platform(), "python": sys.version.split()[0]})
    contract_version: str = EXPERIMENT_VERSION

    @property
    def run_id(self) -> str:
        return canonical_hash(asdict(self))


def relevance_map(query: JudgedQuery) -> dict[str, int]:
    return {item.document_id: item.grade for item in query.judgments}


def dcg(grades: list[int]) -> float:
    return sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(grades))


def retrieval_metrics(query: JudgedQuery, ranked_ids: list[str], k: int = 10, recall_k: int = 20) -> dict[str, float]:
    grades = relevance_map(query)
    relevant = {doc_id for doc_id, grade in grades.items() if grade >= 2}
    top = ranked_ids[:k]
    top_relevant = [doc_id for doc_id in top if doc_id in relevant]
    ranked_grades = [grades.get(doc_id, 0) for doc_id in top]
    ideal = sorted(grades.values(), reverse=True)[:k]
    reciprocal = next((1 / (index + 1) for index, doc_id in enumerate(ranked_ids) if doc_id in relevant), 0.0)
    recall_hits = len(set(ranked_ids[:recall_k]).intersection(relevant))
    primary = {doc_id for doc_id, grade in grades.items() if grade == 3}
    return {
        f"precision@{k}": len(top_relevant) / max(1, len(top)),
        f"recall@{recall_k}": recall_hits / max(1, len(relevant)),
        "mrr": reciprocal,
        f"ndcg@{k}": dcg(ranked_grades) / max(dcg(ideal), 1e-12),
        f"hit_rate@{k}": float(bool(top_relevant)),
        f"primary_coverage@{k}": len(set(top).intersection(primary)) / max(1, len(primary)),
        f"false_primary_support@{k}": float(not query.answerable and any(grades.get(doc_id, 0) >= 2 for doc_id in top)),
    }


def constraint_accuracy(query: JudgedQuery, results: list[dict[str, Any]]) -> float:
    if not results:
        return 1.0
    for result in results:
        metadata = result.get("metadata") or {}
        if query.expected_speakers and metadata.get("speaker") not in query.expected_speakers:
            return 0.0
        date = str(metadata.get("episode_date") or "")
        if query.date_start and date < query.date_start:
            return 0.0
        if query.date_end and date > query.date_end:
            return 0.0
    return 1.0


def redundancy(results: list[dict[str, Any]]) -> float:
    if len(results) < 2:
        return 0.0
    identities = [str(item.get("source_span_id") or item.get("document_id") or item.get("id") or "") for item in results]
    return 1.0 - (len(set(identities)) / len(identities))


def aggregate_metric(rows: list[dict[str, float]], name: str) -> float:
    values = [row[name] for row in rows if name in row]
    return statistics.fmean(values) if values else 0.0


def paired_bootstrap(baseline: list[float], candidate: list[float], samples: int = 10_000, confidence: float = 0.95, seed: int = 42) -> dict[str, Any]:
    if len(baseline) != len(candidate) or not baseline:
        raise ValueError("Paired bootstrap requires non-empty equal-length samples")
    rng = random.Random(seed)
    deltas = []
    for _ in range(samples):
        indices = [rng.randrange(len(baseline)) for _ in baseline]
        deltas.append(statistics.fmean(candidate[index] - baseline[index] for index in indices))
    deltas.sort()
    alpha = (1.0 - confidence) / 2.0
    low = deltas[int(alpha * (len(deltas) - 1))]
    high = deltas[int((1.0 - alpha) * (len(deltas) - 1))]
    return {"mean_delta": statistics.fmean(c - b for b, c in zip(baseline, candidate)), "confidence": confidence, "low": low, "high": high, "samples": samples, "paired_queries": len(baseline), "descriptive_only": len(baseline) < 30, "seed": seed}


def promotion_decision(baseline: dict[str, float], candidate: dict[str, float]) -> dict[str, Any]:
    failures = []
    if candidate.get("ndcg@10", 0) < baseline.get("ndcg@10", 0):
        failures.append("nDCG@10 regressed")
    if candidate.get("recall@20", 0) < baseline.get("recall@20", 0):
        failures.append("Recall@20 regressed")
    if candidate.get("constraint_accuracy", 0) < 1.0:
        failures.append("Hard-filter correctness is below 100%")
    base_latency = baseline.get("median_latency_ms", 0)
    if base_latency and candidate.get("median_latency_ms", 0) > base_latency * 1.25:
        failures.append("Median latency regressed by more than 25%")
    if candidate.get("false_primary_support", 0) > baseline.get("false_primary_support", 0):
        failures.append("No-answer false support regressed")
    return {"promote": not failures, "failures": failures, "warnings": []}
