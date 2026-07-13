# State-of-the-Art Implementation Plan: RAGScope

Last updated: July 2026

## Objective

Turn RAGScope from an exploratory Chroma inspection workbench into the reproducible evaluation authority for the podcast RAG ecosystem. The plan prioritizes self-contained experiment lineage, metrics, projection diagnostics, and comparison tooling before introducing shared run contracts or automated LLM judges.

## Guiding Constraints

- Preserve exploratory workflows while adding a distinct benchmark/evaluation workflow.
- Never treat a 2D/3D projection as ground truth about the original embedding space.
- Keep human judgments versioned and separate from model-generated labels.
- Report component metrics and uncertainty rather than one aggregate score.
- Every comparison must identify corpus, index, model, parameters, seed, code version, and hardware context.
- External systems should integrate through a normalized run schema before RAGScope embeds their execution logic.

## Phase Summary

| Phase | Capability | Effort | Scope | Other repositories touched |
|---|---|---|---|---|
| 1 | Immutable experiment manifests | Easy-medium | Repo-local | None |
| 2 | Judged-query dataset model and editor | Medium | Repo-local | None |
| 3 | Classical retrieval metrics | Medium | Repo-local | None |
| 4 | Side-by-side comparison and statistics | Medium | Repo-local | None |
| 5 | Projection quality and stability | Medium | Repo-local | None |
| 6 | Cluster stability and data-quality diagnostics | Medium | Repo-local | None |
| 7 | Deterministic explainability | Medium | Repo-local | None |
| 8 | Continuous local/CI evaluation | Medium | Repo-local | None initially |
| 9 | Shared run-trace ingestion | Medium | Multi-repo | `PodCast Chat`, `Chroma DB Import` |
| 10 | Hybrid/reranker evaluation providers | Medium | Multi-repo | `PodCast Chat`, `Chroma DB Import` |
| 11 | Answer and citation evaluation | Medium-hard | Multi-repo | `PodCast Chat`, `Podcast-RAG-pipeline`, `Chroma DB Import` |
| 12 | Calibrated automated judges | Hard | Multi-repo | `PodCast Chat`; optionally model-serving infrastructure |
| 13 | Graph/adaptive retrieval evaluation | Hard | Multi-repo | `PodCast Chat`, `Chroma DB Import`, `Podcast-RAG-pipeline` |
| 14 | Source attribution and counterfactual evaluation | Hard | Multi-repo | `PodCast Chat` |

## Phase 1: Immutable Experiment Manifests

Scope: repo-local.

Make every saved retrieval experiment reproducible and comparable.

Deliverables:

- Define a versioned experiment schema containing corpus fingerprint, collection, document count, schema version, embedding identity/dimension, retrieval settings, projection/clustering settings, seeds, timestamps, code/build identity, and hardware summary.
- Separate immutable run data from mutable user notes and labels.
- Compute a canonical run ID from configuration and input fingerprints.
- Add migration support for existing saved retrieval reports.
- Add a manifest inspector and compatibility warnings in the UI.

Tests and exit criteria:

- Saving the same deterministic run produces the same configuration fingerprint.
- Notes can change without altering immutable run identity.
- Missing critical lineage fields are visibly marked unknown.
- Legacy reports remain readable.

## Phase 2: Judged-Query Dataset Model and Editor

Scope: repo-local.

Create the benchmark foundation without requiring other apps to change.

Deliverables:

- Define a JSON schema for query text, query class, expected speakers/dates, answerability, graded relevant document IDs, stable source IDs, acceptable evidence sets, reference claims, and reviewer metadata.
- Add import/export and schema validation.
- Build a UI workflow to create queries from selected documents, grade candidates, add hard negatives, and adjudicate disagreements.
- Track dataset version, corpus compatibility, judgment provenance, and review status.
- Support multiple valid evidence sets and partial relevance for hierarchical records.

Tests and exit criteria:

- Dataset round-trip preserves judgments and reviewer state.
- Stale/missing document IDs are reported without losing source-level judgments.
- Human and synthetic questions are clearly labeled and filterable.
- A starter set can be executed against the current semantic search path.

## Phase 3: Classical Retrieval Metrics

Scope: repo-local.

Measure the existing retrieval experiments against judged queries.

Deliverables:

- Implement Recall@k, Precision@k, MRR, nDCG, hit rate, graded gain, and no-answer false-positive rate.
- Add speaker/date constraint accuracy, node-type coverage, primary-evidence coverage, and result redundancy.
- Report per-query, per-class, and aggregate outcomes.
- Make `k` values configurable and preserve raw ranked lists.
- Add metric unit tests with hand-computed fixtures.

Tests and exit criteria:

- Metric outputs match independent hand calculations.
- Empty, unanswerable, tied, and partially relevant cases are defined explicitly.
- Aggregate metrics link back to every contributing query.

## Phase 4: Side-by-Side Comparison and Statistics

Scope: repo-local.

Turn saved runs into defensible decisions.

Deliverables:

- Add run selection and compatibility checks for paired comparisons.
- Show per-query deltas, wins/losses/ties, worst regressions, and query-class breakdowns.
- Add paired bootstrap confidence intervals with fixed recorded seeds.
- Add quality/latency/storage Pareto views.
- Allow a primary metric and explicit regression guardrails to be configured.
- Export a Markdown and JSON promotion report.

Tests and exit criteria:

- Incompatible corpora or judged-set versions cannot be compared silently.
- Bootstrap results are reproducible from the recorded seed.
- Reports expose raw per-query values and excluded cases.

## Phase 5: Projection Quality and Stability

Scope: repo-local.

Make UMAP/PCA views safer to interpret.

Deliverables:

- Record and expose all reducer parameters and random seeds.
- Compute trustworthiness and k-neighbor preservation between high-dimensional embeddings and projected coordinates.
- Add a multi-seed stability run for UMAP and compare neighbor overlap.
- Link projected points to their true high-dimensional nearest neighbors.
- Add warnings when sample size or quality scores make the view unreliable.

Tests and exit criteria:

- Projection metrics use the same filtered population shown in the plot.
- Cached results include seed and reducer version.
- Stability runs do not overwrite the primary projection.
- UI language distinguishes visual proximity from embedding similarity.

## Phase 6: Cluster Stability and Data-Quality Diagnostics

Scope: repo-local.

Evaluate whether clusters and embedding geometry are stable and useful.

Deliverables:

- Add repeated/bootstrapped clustering runs and agreement metrics such as adjusted mutual information.
- Add silhouette or density-validity measures where mathematically appropriate.
- Report cluster composition by speaker, episode, date, and node type.
- Add embedding norm distribution, anisotropy indicators, nearest-neighbor hubness, duplicate rate, and coverage gaps.
- Compare diagnostics across embedding/index versions loaded separately.

Tests and exit criteria:

- Metrics clearly mark algorithms/cases where they are not valid.
- Cluster labels are kept separate from cluster-quality scores.
- Sampling and seeds are recorded.
- Large datasets can use bounded samples without blocking the UI.

## Phase 7: Deterministic Explainability

Scope: repo-local.

Explain retrieval using recorded system signals before adding expensive model attribution.

Deliverables:

- Define a normalized score breakdown containing query variant, filters, candidate pool, raw similarity, normalization, fusion contribution, reranker score, diversity penalty, and hierarchy expansion path.
- Extend the existing "why" panel to show available fields and explicitly mark unavailable stages.
- Add overlap/redundancy views for selected evidence sets.
- Add counterfactual retrieval controls that remove one filter or channel and rerun retrieval, without invoking a generator.
- Export explanation records with experiment manifests.

Tests and exit criteria:

- Explanations reconstruct final rank from recorded deterministic stages where possible.
- Missing stages are not inferred or fabricated.
- Counterfactual runs retain a link to the parent experiment.

## Phase 8: Continuous Local and CI Evaluation

Scope: repo-local initially.

Make regressions visible without requiring the full UI.

Deliverables:

- Add a headless benchmark command for judged retrieval sets.
- Define a small deterministic fixture suite suitable for CI.
- Define a larger on-demand suite for real local Chroma collections.
- Emit machine-readable exit criteria and human-readable reports.
- Support baseline snapshots and configurable regression thresholds.

Tests and exit criteria:

- CI suite has no network or GPU requirement.
- Full suites record hardware and dependency versions.
- A regression failure identifies affected queries and metrics.

## Phase 9: Shared Run-Trace Ingestion

Scope: multi-repo.

Touched repositories:

- `PodCast Chat`: exports retrieval, context, generation, citation, and timing traces.
- `Chroma DB Import`: exports corpus/index manifests and build metrics.
- `RAGScope`: validates, stores, compares, and visualizes both trace types.

Deliverables:

- Agree on versioned JSON schemas and shared fixtures.
- Add an ingestion API/UI with validation and migration errors.
- Link chat runs to exact importer manifests and judged queries.
- Preserve unknown extension fields for forward compatibility.
- Add contract tests in every touched repository.

Tests and exit criteria:

- RAGScope imports representative traces from both repositories without manual conversion.
- Corpus/index mismatches are detected before scoring.
- Round-tripped traces preserve all ranking and evidence information.

## Phase 10: Hybrid and Reranker Evaluation Providers

Scope: multi-repo.

Touched repositories:

- `Chroma DB Import`: creates lexical and alternate dense indexes.
- `PodCast Chat`: runs dense, lexical, fused, and reranked retrieval.
- `RAGScope`: evaluates and explains those runs.

Deliverables:

- Add channel-aware metrics and ablations for dense-only, lexical-only, fused, and reranked candidates.
- Visualize candidate overlap, unique relevant finds, rank movement, and latency by stage.
- Compare contextual-header and embedding-model shadow indexes.
- Produce promotion reports with quality, storage, build time, and query latency.

Tests and exit criteria:

- Fused rankings are reproducible from trace inputs.
- Ablation reports isolate the contribution of each channel and reranker.
- Index promotion criteria are machine-readable.

## Phase 11: Answer and Citation Evaluation

Effort: medium-hard. Scope: multi-repo.

Touched repositories:

- `PodCast Chat`: emits structured answers and evidence IDs.
- `Podcast-RAG-pipeline`: supplies primary evidence links and stable source spans.
- `Chroma DB Import`: validates and packages provenance.
- `RAGScope`: scores answer and citation outcomes.

Deliverables:

- Add answer relevance, claim completeness, citation precision/recall, unsupported citation rate, and abstention metrics.
- Support human claim/evidence grading and adjudication.
- Distinguish citations to derived summaries from primary transcript evidence.
- Add per-claim audit views connecting answer text to evidence.
- Track evaluator identity and calibration status.

Exit criteria:

- Every automated score can be inspected at claim/evidence level.
- Human-reviewed calibration samples are versioned.
- Citation metrics handle multiple acceptable evidence sets.

## Phase 12: Calibrated Automated Judges

Effort: hard. Scope: multi-repo.

Touched repositories: `PodCast Chat` and any local model-serving configuration used for evaluation.

Deliverables:

- Add pluggable judge providers for context relevance, faithfulness, answer relevance, and completeness.
- Build synthetic training/calibration data only from clearly labeled sources.
- Compare judge outputs with a human-reviewed set and report agreement/confusion.
- Use prediction-powered or other calibrated estimates where appropriate.
- Cache judgments by prompt, model, and evidence fingerprint.

Decision gate: automated judges may expand coverage but may not replace the human-labeled calibration core or classical retrieval metrics.

## Phase 13: Graph and Adaptive Retrieval Evaluation

Effort: hard. Scope: multi-repo.

Touched repositories: `PodCast Chat`, `Chroma DB Import`, and `Podcast-RAG-pipeline`.

Deliverables:

- Extend run traces with query routing, graph paths, expansion candidates, correction actions, and model-call counts.
- Add query classes for factual, temporal, associative, global, contradiction, and unanswerable tasks.
- Score initial retrieval, expanded retrieval, final evidence, answer, and latency independently.
- Add graph path relevance and correction utility metrics.
- Compare bounded adaptive systems against equivalent fixed-compute baselines.

Decision gate: added inference steps must show gains beyond those attributable to larger candidate counts or stronger generators.

## Phase 14: Source Attribution and Counterfactual Evaluation

Effort: hard. Scope: multi-repo.

Touched repository: `PodCast Chat` for controlled regeneration and evidence-removal runs.

Deliverables:

- Add selected-case leave-one-evidence-out generation experiments.
- Compare deterministic retrieval provenance with observed answer changes.
- Evaluate affordable attribution approximations before Shapley-style methods.
- Report instability and interaction effects among redundant/complementary evidence.
- Restrict expensive attribution to explicit audit workflows.

Decision gate: source attribution remains an audit tool unless it is stable, interpretable, and affordable on local hardware.

## Recommended First Release Boundary

The first release should implement Phases 1-4. These are fully contained in RAGScope and create the core evaluation system: immutable lineage, judged queries, classical metrics, and statistically grounded comparisons. Phases 5-8 then strengthen existing visualization and make evaluation continuous without requiring changes elsewhere. Phase 9 is the first mandatory cross-repository milestone.

