import React from "react";

import { INFO_TABS } from "../lib/constants";
import {
  clusterColor,
  hierarchyLabel,
  hierarchyLevel,
  retrievalRankColor,
  rowParentId,
  short,
} from "../lib/helpers";

function InspectTab({ controller }) {
  const { inspectedRow } = controller;

  if (!inspectedRow) {
    return (
      <section>
        <h2>Inspector</h2>
        <p className="muted">Click a point or row to inspect a chunk.</p>
      </section>
    );
  }

  return (
    <section>
      <h2>Inspector</h2>
      <div className="inspector">
        <div className="badge-row">
          <span className="badge">{hierarchyLabel(hierarchyLevel(inspectedRow))}</span>
          <span className="badge">Cluster {inspectedRow.cluster}</span>
          {controller.selectedQuality?.speakers?.slice(0, 3).map((speaker) => <span className="badge" key={speaker}>{speaker}</span>)}
          {inspectedRow["meta.episode_date"] || inspectedRow.metadata?.episode_date ? <span className="badge">{inspectedRow["meta.episode_date"] || inspectedRow.metadata?.episode_date}</span> : null}
        </div>
        <dl>
          <dt>ID</dt><dd>{inspectedRow.id}</dd>
          <dt>Rank</dt><dd>{controller.retrievalRankById.has(String(inspectedRow.id)) ? `#${controller.retrievalRankById.get(String(inspectedRow.id))} · ${controller.retrievalScoreById.get(String(inspectedRow.id))}` : "Not ranked"}</dd>
          <dt>Level</dt><dd>{hierarchyLabel(hierarchyLevel(inspectedRow))}</dd>
          <dt>Cluster</dt><dd><span className="swatch" style={{ background: clusterColor(inspectedRow.cluster, controller.colorMap) }} />{inspectedRow.cluster}</dd>
          <dt>Source</dt><dd>{inspectedRow.source || "Unknown"}</dd>
          <dt>Title</dt><dd>{inspectedRow.title || "Untitled"}</dd>
        </dl>
        <h3>Chunk quality</h3>
        {controller.selectedQuality ? (
          <div className="quality-grid">
            <span><strong>{controller.selectedQuality.textLength.toLocaleString()}</strong><small>chars</small></span>
            <span><strong>{controller.selectedQuality.tokenEstimate.toLocaleString()}</strong><small>est. tokens</small></span>
            <span><strong>{controller.selectedQuality.speakerCount}</strong><small>speakers</small></span>
            <span><strong>{controller.selectedQuality.duration === null ? "n/a" : `${controller.selectedQuality.duration.toFixed(1)}s`}</strong><small>duration</small></span>
            <span><strong>{controller.selectedQuality.parentCount}</strong><small>parents</small></span>
            <span><strong>{controller.selectedQuality.childCount}</strong><small>children</small></span>
            <span><strong>{controller.selectedQuality.parentSimilarity === null ? "n/a" : controller.selectedQuality.parentSimilarity.toFixed(3)}</strong><small>parent fit</small></span>
            <span><strong>{controller.selectedQuality.nearest ? controller.selectedQuality.nearest.similarity.toFixed(3) : "n/a"}</strong><small>nearest fit</small></span>
          </div>
        ) : <p className="muted">Quality metrics are available after a dataset is loaded.</p>}
        <h3>Why this result?</h3>
        {controller.whyResult ? (
          <div className="why-panel">
            <p className="muted">Transparent non-LLM diagnostics for the selected chunk.</p>
            <div className="tag-list">
              {(controller.whyResult.overlap.length ? controller.whyResult.overlap : ["no direct query term overlap"]).map((term) => <span className="tag" key={term}>{term}</span>)}
            </div>
            <dl>
              <dt>Score</dt><dd>{controller.whyResult.score === undefined ? "Not in current ranked run" : `${controller.whyResult.score} (#${controller.whyResult.rank})`}</dd>
              <dt>Topic</dt><dd>{controller.whyResult.topic || "No topic label"}</dd>
              <dt>Location</dt><dd>{controller.whyResult.level} · cluster {controller.whyResult.cluster}</dd>
              <dt>Neighbor</dt><dd>{controller.whyResult.nearest ? `${controller.whyResult.nearest.row.id} · ${controller.whyResult.nearest.similarity.toFixed(3)}` : "Not computed"}</dd>
            </dl>
            {!!controller.whyResult.metadataOverlaps.length && (
              <table className="mini-table"><tbody>{controller.whyResult.metadataOverlaps.map(([key, value]) => (
                <tr key={key}><td>{key}</td><td>{String(value)}</td></tr>
              ))}</tbody></table>
            )}
          </div>
        ) : <p className="muted">Select a search result to explain score, context, and neighborhood.</p>}
        <h3>Chunk text</h3>
        <pre>{controller.inspectorLoading ? "Loading chunk text..." : controller.inspectedDocument?.document || inspectedRow.preview}</pre>
        <h3>Metadata</h3>
        <pre>{JSON.stringify(controller.inspectedDocument?.metadata || inspectedRow.metadata || {}, null, 2)}</pre>
      </div>
    </section>
  );
}

function AnalyzeTab({ controller }) {
  return (
    <>
      <section>
        <div className="section-heading-row">
          <h2>Selection Analysis</h2>
          <button type="button" className="compact-button" onClick={() => controller.handleAnalyzeSelection()} disabled={!controller.canAnalyzeSelection || controller.analysisLoading}>
            {controller.analysisLoading ? "Analyzing..." : controller.explicitSelectedIds.length ? "Analyze" : controller.activeSearchIds.length ? "Analyze Results" : controller.selectedCluster !== "" ? "Analyze Cluster" : "Analyze"}
          </button>
        </div>
        {controller.analysisResult ? (
          <div className="analysis-panel">
            <p className="muted">{controller.analysisResult.selected_count} selected of {controller.analysisResult.total_count} chunks ({controller.analysisResult.coverage_percent}%).</p>
            <h3>Distinctive Terms</h3>
            <div className="tag-list">
              {(controller.analysisResult.keywords || []).slice(0, 12).map((item) => <span className="tag" key={item.term}>{item.term}</span>)}
            </div>
            <h3>Shared Signals</h3>
            {(controller.analysisResult.common_metadata || []).length ? (
              <table className="mini-table"><tbody>{(controller.analysisResult.common_metadata || []).slice(0, 8).map((item) => (
                <tr key={`${item.field}-${item.value}`}><td>{item.field}</td><td>{item.value}</td><td>{item.selected_percent}%</td></tr>
              ))}</tbody></table>
            ) : <p className="muted">No high-value metadata commonality found.</p>}
            <h3>Dominant Topics</h3>
            <ul className="plain-list">{(controller.analysisResult.dominant_topics || []).slice(0, 6).map((item) => <li key={item.value}>{item.value || "Untitled"} ({item.selected_count})</li>)}</ul>
            <h3>Date Ranges</h3>
            <ul className="plain-list">
              {(controller.analysisResult.date_ranges || []).map((item) => <li key={item.field}>{item.field}: {item.start} to {item.end}</li>)}
              {!(controller.analysisResult.date_ranges || []).length && <li>No date-like selection fields found.</li>}
            </ul>
            <h3>Representative Chunks</h3>
            <div className="representative-list">
              {(controller.analysisResult.representative_chunks || []).slice(0, 5).map((item) => (
                <button type="button" key={item.id} onClick={() => {
                  const row = controller.rowById.get(String(item.id));
                  if (row) controller.setInspectedRow(row);
                }}>
                  <strong>{item.title || item.source || item.id}</strong>
                  <span>{item.preview}</span>
                </button>
              ))}
            </div>
          </div>
        ) : <p className="muted">Select chart points, table rows, search results, or a cluster topic, then analyze commonality.</p>}
      </section>
      <section>
        <h2>Cluster Topics</h2>
        <div className="cluster-list">
          <button type="button" className={controller.selectedCluster === "" ? "cluster active" : "cluster"} onClick={() => controller.setSelectedCluster("")}>
            <span className="swatch neutral" />All clusters
          </button>
          {controller.clusterRows.map((topic) => (
            <button type="button" key={topic.cluster} className={String(controller.selectedCluster) === String(topic.cluster) ? "cluster active" : "cluster"} onClick={() => controller.setSelectedCluster(String(topic.cluster))}>
              <span className="swatch" style={{ background: topic.color }} />
              <span><strong>{topic.label}</strong><small>Cluster {topic.cluster} · {topic.count} chunks</small></span>
              <span className="cluster-analyze" title="Analyze this cluster topic" onClick={(event) => {
                event.stopPropagation();
                const clusterIds = controller.sourceRows.filter((row) => String(row.cluster) === String(topic.cluster)).map((row) => String(row.id));
                controller.setSelectedCluster(String(topic.cluster));
                controller.setChartSelectedIds([]);
                controller.setTableSelectedIds([]);
                controller.handleAnalyzeSelection(clusterIds);
              }}>Analyze</span>
            </button>
          ))}
        </div>
      </section>
      <section>
        <h2>Outliers & Orphans</h2>
        <p className="muted">Outliers use projected nearest-neighbor distance; orphans are nodes whose parent id is not present in the loaded dataset.</p>
        <div className="quality-list">
          {controller.outlierRows.slice(0, 8).map((item) => (
            <button type="button" key={item.row.id} onClick={() => {
              controller.setInspectedRow(item.row);
              controller.setChartSelectedIds([String(item.row.id)]);
              controller.setInfoTab("Inspect");
            }}>
              <strong>{item.orphan ? "Orphan + outlier" : "Outlier"} · {item.nearest.similarity.toFixed(3)} nearest fit</strong>
              <small>{hierarchyLabel(hierarchyLevel(item.row))}: {short(item.row.preview, 120)}</small>
            </button>
          ))}
          {!controller.outlierRows.length && <p className="muted">No outlier candidates available.</p>}
        </div>
        {!!controller.orphanRows.length && (
          <>
            <h3>Hierarchy Orphans</h3>
            <div className="quality-list">
              {controller.orphanRows.slice(0, 6).map((row) => (
                <button type="button" key={row.id} onClick={() => {
                  controller.setInspectedRow(row);
                  controller.setChartSelectedIds([String(row.id)]);
                  controller.setInfoTab("Inspect");
                }}>
                  <strong>{rowParentId(row)}</strong>
                  <small>{short(row.preview, 120)}</small>
                </button>
              ))}
            </div>
          </>
        )}
      </section>
    </>
  );
}

function RetrievalTab({ controller }) {
  return (
    <section>
      <div className="section-heading-row">
        <h2>Retrieval Experiment</h2>
        <div className="button-row">
          <button type="button" className="compact-button" onClick={controller.handleRetrievalExperiment} disabled={!controller.prefs.semanticSearch.trim() || controller.retrievalLoading}>
            {controller.retrievalLoading ? "Scoring..." : "Run"}
          </button>
          <button type="button" className="compact-button" onClick={controller.saveRetrievalRun} disabled={!controller.retrievalResult}>Save</button>
          <button type="button" className="compact-button" onClick={controller.exportRetrievalReport} disabled={!controller.retrievalResult}>Export</button>
        </div>
      </div>
      <p className="muted">Scores the current filtered candidate set against the semantic query and overlays ranked results on the chart.</p>
      {controller.retrievalResult ? (
        <div className="retrieval-panel">
          <div className="metric-grid">
            <span><strong>{controller.retrievalResult.candidate_count?.toLocaleString?.() || 0}</strong><small>candidates</small></span>
            <span><strong>{(controller.retrievalResult.results || []).length}</strong><small>ranked</small></span>
            <span><strong>{controller.retrievalResult.embedding_dim}</strong><small>dimensions</small></span>
          </div>
          <h3>Score Distribution</h3>
          <div className="histogram">
            {(controller.retrievalResult.histogram || []).map((bucket, index) => {
              const maxCount = Math.max(...(controller.retrievalResult.histogram || []).map((item) => item.count), 1);
              return (
                <div className="histogram-row" key={`${bucket.start}-${bucket.end}-${index}`}>
                  <span>{bucket.start.toFixed?.(2) ?? bucket.start}</span>
                  <div><i style={{ width: `${Math.max(2, (bucket.count / maxCount) * 100)}%` }} /></div>
                  <b>{bucket.count}</b>
                </div>
              );
            })}
          </div>
          <h3>Ranked Results</h3>
          <div className="ranked-list">
            {(controller.retrievalResult.results || []).map((item) => {
              const row = controller.rowById.get(String(item.id));
              return (
                <button type="button" key={item.id} onClick={() => {
                  if (row) controller.setInspectedRow(row);
                  controller.setChartSelectedIds([String(item.id)]);
                  controller.setInfoTab("Inspect");
                }}>
                  <span className="rank-badge" style={{ background: retrievalRankColor(item.rank) }}>#{item.rank}</span>
                  <strong>{item.score.toFixed?.(3) ?? item.score} · {hierarchyLabel(hierarchyLevel(row || item))}</strong>
                  <small>{short(row?.preview || item.preview, 150)}</small>
                </button>
              );
            })}
          </div>
        </div>
      ) : <p className="muted">Run an experiment from this tab or the Search panel to see scores, rank overlays, and distribution shape.</p>}
      <label className="run-notes">
        Run notes
        <textarea value={controller.retrievalNotes} onChange={(event) => controller.setRetrievalNotes(event.target.value)} placeholder="Observations to save with this retrieval run" />
      </label>
      <h3>Saved Retrieval Runs</h3>
      <div className="saved-run-list">
        {controller.savedRuns.slice(0, 8).map((run) => (
          <div className="saved-run" key={run.id}>
            <button type="button" onClick={() => controller.loadRetrievalRun(run)}>
              <strong>{run.name}</strong>
              <small>{new Date(run.timestamp).toLocaleString()} · {run.ids.length} results</small>
            </button>
            <button type="button" className="danger compact-button" onClick={() => controller.setSavedRuns((current) => current.filter((item) => item.id !== run.id))}>Delete</button>
          </div>
        ))}
        {!controller.savedRuns.length && <p className="muted">Saved runs preserve query, filters, top-k, returned ids, scores, and timestamp for later comparison.</p>}
      </div>
    </section>
  );
}

function CompareTab({ controller }) {
  return (
    <section>
      <div className="section-heading-row">
        <h2>Compare Retrieval Modes</h2>
        <button type="button" className="compact-button" onClick={controller.compareRetrievalModes} disabled={!controller.prefs.semanticSearch.trim() || controller.compareLoading}>
          {controller.compareLoading ? "Comparing..." : "Compare"}
        </button>
      </div>
      <p className="muted">Runs the same query across hierarchy-based candidate pools so you can see whether summaries, claims, or leaf chunks dominate retrieval.</p>
      {controller.compareResult ? (
        <div className="compare-grid">
          {controller.compareResult.map((mode) => (
            <div className="compare-card" key={mode.name}>
              <h3>{mode.name}</h3>
              <p className="muted">{mode.candidateCount.toLocaleString()} candidates</p>
              {(mode.result?.results || []).slice(0, 5).map((item) => {
                const row = controller.rowById.get(String(item.id));
                return (
                  <button type="button" key={`${mode.name}-${item.id}`} onClick={() => {
                    controller.setRetrievalResult(mode.result);
                    controller.setHighlightedIds((mode.result?.ids || []).map(String));
                    if (row) controller.setInspectedRow(row);
                    controller.setInfoTab("Inspect");
                  }}>
                    <span className="rank-badge" style={{ background: retrievalRankColor(item.rank) }}>#{item.rank}</span>
                    <strong>{item.score.toFixed?.(3) ?? item.score}</strong>
                    <small>{hierarchyLabel(hierarchyLevel(row || item))}: {short(row?.preview || item.preview, 110)}</small>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      ) : <p className="muted">Enter a semantic query and compare retrieval modes.</p>}
    </section>
  );
}

function HierarchyTab({ controller }) {
  return (
    <section>
      <h2>Result Path</h2>
      <p className="muted">Shows the selected result in its RAG hierarchy, from higher-level summary nodes down to the inspected chunk when parent metadata is available.</p>
      {controller.hierarchyTrace.length ? (
        <div className="path-trace">
          {controller.hierarchyTrace.map((row, index) => (
            <button type="button" key={`${row.id}-${index}`} onClick={() => {
              controller.setInspectedRow(row);
              controller.setInfoTab("Inspect");
            }}>
              <span className="path-level">{hierarchyLabel(hierarchyLevel(row))}</span>
              <strong>{row.title || row.source || row.id}</strong>
              <small>{short(row.preview, 150)}</small>
            </button>
          ))}
        </div>
      ) : <p className="muted">Select a point, table row, or retrieval result to trace its parent path.</p>}
    </section>
  );
}

export function InfoPanel({ controller }) {
  // The right rail groups evidence by investigative question: what is this chunk,
  // what does the selection share, how did retrieval behave, and where does it sit in the hierarchy.
  const tabs = {
    Inspect: <InspectTab controller={controller} />,
    Analyze: <AnalyzeTab controller={controller} />,
    Retrieval: <RetrievalTab controller={controller} />,
    Compare: <CompareTab controller={controller} />,
    Hierarchy: <HierarchyTab controller={controller} />,
  };

  return (
    <aside className="info-panel" style={{ width: controller.rightWidth }}>
      <div className="info-tabs">
        {INFO_TABS.map((tab) => (
          <button type="button" key={tab} className={controller.infoTab === tab ? "active" : ""} onClick={() => controller.setInfoTab(tab)}>
            {tab}
          </button>
        ))}
      </div>
      {tabs[controller.infoTab]}
    </aside>
  );
}
