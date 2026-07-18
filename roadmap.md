# Roadmap

Updated: 2026-07-17

`RAGScope` is the evaluation authority and investigation workbench for the podcast ecosystem. Judged datasets, immutable experiment identity, paired metrics, promotion guardrails, provenance tracing, shared local evaluation packs, contract fixtures, and reproducible visual diagnostics are implemented. The highest-value next step is to turn these capabilities into a routine human review and release process.

## Product Direction

- Make deterministic evidence and human judgments authoritative; keep LLM interpretation advisory.
- Align comparisons by corpus, pack, query set, representation, and run identity.
- Route failures back to the repository and artifact that can actually fix them.
- Keep private packs local while making schemas, aggregate reports, and synthetic regressions portable.
- Treat projections and clusters as diagnostic views, not retrieval-quality proof.

## Current Foundation

- React/FastAPI workbench for Chroma loading, filtering, search, maps, clusters, saved views, and audits.
- Versioned judged datasets, ranked-candidate grading, retrieval metrics, paired bootstrap comparisons, Pareto views, and promotion guardrails.
- Immutable experiment manifests, mutable notes separation, fingerprints, seeds, timings, runtime metadata, and report export.
- Chroma import-manifest inspection, hard-versus-incomplete contract diagnostics, and vector-to-transcript provenance tracing.
- Local-reference `podcast-evaluation-pack-v1` schema, CLI/API validation, readiness reporting, and normalized cross-system run identity.
- Synthetic baselines, cross-repository trace fixtures, frontend builds, and clean-machine diagnostics.

## Value-Ordered Priorities

### 1. Build the evaluation campaign workspace

- Add UI workflows to create/import local packs, inspect sampling targets, validate paths/hashes, and manage adjudication queues.
- Show readiness separately for transcription, retrieval, grounding, answer quality, provider comparisons, and release-critical subsets.
- Run and compare baseline/candidate campaigns from one queue with immutable identities and resumable status.
- Make private-data boundaries and exportable aggregate fields explicit.

### 2. Centralize end-to-end quality and regression triage

- Ingest transcription reports, processed-cache deltas, import manifests, Chat traces, and ecosystem reports under one corpus release.
- Attribute each failure to likely audio/transcript, processing, representation, import, retrieval, grounding, or generation causes.
- Add per-query history, regression ownership, severity, review status, and links to upstream evidence/workbenches.
- Detect judgments made stale by source corrections or corpus release changes.

### 3. Operationalize promotion decisions

- Add configurable release gates for critical queries, condition slices, quality deltas, latency, memory, storage, and failure rates.
- Require aligned identities and minimum reviewed coverage before promotion.
- Generate concise candidate decision reports with wins, regressions, confidence intervals, exclusions, and rollback recommendation.
- Keep LLM judge calibration visible and prevent advisory scores from silently becoming authoritative.

### 4. Scale analysis without losing reproducibility

- Add server-side pagination, background jobs, cancellation, progress, bounded caches, and large-collection diagnostics.
- Store reusable retrieval result sets so metric and UI work does not repeatedly query the vector store.
- Add temporal, hierarchy, duplicate, contradiction, and corpus-diff views with explicit scope labels.
- Preserve reducer/clustering seeds and distinguish visualization changes from retrieval changes.

### 5. Improve collaboration, export, and privacy

- Add portable campaign/report bundles with redaction and no private media by default.
- Support review assignments and stable pseudonyms without requiring a cloud service.
- Add retention/deletion controls for packs, traces, generated queries, model diagnostics, and cached documents.
- Provide a read-only report mode suitable for sharing approved aggregate findings.

### 6. Package after operational proof

- Validate large collections, frontend/backend lifecycle, report exports, and cache cleanup on a separate Windows target.
- Bundle diagnostics and schema migrations without bundling private datasets, credentials, or model weights.
- Keep CLI/API workflows available for automation and CI alongside the desktop workbench.

## Sequencing

1. Ship the evaluation campaign and local-pack review UI.
2. Record the first private end-to-end corpus baseline.
3. Ingest all component artifacts and build regression triage/history.
4. Enforce promotion gates across quality and operational cost.
5. Scale background analysis and add corpus/temporal diagnostics.
6. Complete privacy-aware report sharing and target-machine packaging.

The ecosystem-level sequence and promotion rules live in `../PODCAST_ECOSYSTEM_ROADMAP.md` when these repositories share a workspace.
## Phases 0–2 implementation status (2026-07-17)

Campaign contracts, migrations, backend/API, campaign workspace, identity graph, stale-review blocking, human decision, and portable export are implemented. The real baseline/correction campaign awaits the approved private evaluation pack.
