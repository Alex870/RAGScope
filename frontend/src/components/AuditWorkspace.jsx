import React from "react";

import { short } from "../lib/helpers";

export function AuditWorkspace({ controller }) {
  const { auditReport } = controller;

  if (!auditReport) {
    return (
      <section className="audit-workspace">
        <div className="empty-state">
          <h2>No audit report yet</h2>
          <p>Open the Audit section in the sidebar and run a deterministic Phase 1 audit.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="audit-workspace">
      <div className="audit-hero">
        <div>
          <h2>RAG Quality Audit</h2>
          <p>{auditReport.collection} · {auditReport.preset} · {new Date(auditReport.timestamp).toLocaleString()}</p>
        </div>
        <div className="audit-score">{auditReport.scores.overall}</div>
      </div>
      <div className="audit-score-grid">
        {Object.entries(auditReport.scores).map(([key, value]) => (
          <span key={key}><strong>{value}</strong><small>{key}</small></span>
        ))}
      </div>
      <div className="audit-actions">
        <button type="button" onClick={() => controller.exportAuditReport("md")}>Export Markdown</button>
        <button type="button" onClick={() => controller.exportAuditReport("json")}>Export JSON</button>
        <button type="button" onClick={() => controller.setWorkspaceMode("Explore")}>Return to Explore</button>
      </div>
      <div className="audit-grid">
        <div className="audit-column">
          <section>
            <h3>Summary</h3>
            <dl className="audit-dl">
              <dt>Loaded chunks</dt><dd>{auditReport.database.loadedRows.toLocaleString()}</dd>
              <dt>Embedding dim</dt><dd>{auditReport.database.embeddingDimension || "unknown"}</dd>
              <dt>Clusterer</dt><dd>{auditReport.database.clusterer || "unknown"}</dd>
              <dt>Clusters</dt><dd>{auditReport.database.clusters}</dd>
              <dt>Speakers</dt><dd>{auditReport.database.speakers}</dd>
            </dl>
            <h3>Findings</h3>
            <ul className="plain-list">
              {auditReport.findings.length ? auditReport.findings.map((finding) => <li key={finding}>{finding}</li>) : <li>No major deterministic findings.</li>}
            </ul>
          </section>
          <section>
            <h3>Embeddings & Structure</h3>
            <dl className="audit-dl">
              <dt>Outliers</dt><dd>{auditReport.embeddings.outlierCount}</dd>
              <dt>Orphans</dt><dd>{auditReport.hierarchy.orphanCount}</dd>
              <dt>Duplicate groups</dt><dd>{auditReport.embeddings.duplicates.length}</dd>
            </dl>
            <div className="quality-list">
              {auditReport.embeddings.outlierExamples.slice(0, 5).map((item) => (
                <button type="button" key={item.id} onClick={() => {
                  const row = controller.rowById.get(String(item.id));
                  if (row) {
                    controller.setInspectedRow(row);
                    controller.setChartSelectedIds([String(item.id)]);
                    controller.setWorkspaceMode("Explore");
                    controller.setInfoTab("Inspect");
                  }
                }}>
                  <strong>{item.level} · fit {Number(item.nearestFit).toFixed(3)}</strong>
                  <small>{short(item.preview, 120)}</small>
                </button>
              ))}
            </div>
          </section>
          {auditReport.llm?.enabled && (
            <section>
              <h3>LLM Interpretation</h3>
              {auditReport.llm.diagnostics?.warnings?.length ? (
                <div className="inline-warning">
                  <strong>LLM diagnostics</strong>
                  <ul className="plain-list">
                    {auditReport.llm.diagnostics.warnings.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                  <button type="button" onClick={() => controller.setMessageModal({ title: "LLM Raw Output", text: auditReport.llm.raw || "" })}>
                    View raw output
                  </button>
                </div>
              ) : null}
              <p className="muted">{auditReport.llm.summary || "No summary returned."}</p>
              <h3>Strengths</h3>
              <ul className="plain-list">
                {(auditReport.llm.strengths || []).map((item) => <li key={item}>{item}</li>)}
              </ul>
              <h3>Risks</h3>
              <ul className="plain-list">
                {(auditReport.llm.risks || []).map((item) => <li key={item}>{item}</li>)}
              </ul>
              <h3>Recommended Actions</h3>
              <ul className="plain-list">
                {(auditReport.llm.recommended_actions || []).map((item) => <li key={item}>{item}</li>)}
              </ul>
              <h3>Query Judgements</h3>
              <table className="mini-table">
                <tbody>{(auditReport.llm.query_judgements || []).map((item, index) => (
                  <tr key={`${item.query || "query"}-${index}`}><td>{item.rating_1_to_5 || "n/a"}/5</td><td>{item.query}</td><td>{item.note}</td></tr>
                ))}</tbody>
              </table>
            </section>
          )}
        </div>
        <div className="audit-column">
          <section>
            <h3>Metadata Completeness</h3>
            <table className="mini-table">
              <tbody>{auditReport.metadata.requiredFields.map((item) => (
                <tr key={item.field}><td>{item.field}</td><td>{item.completeness}%</td><td>{item.missing} missing</td></tr>
              ))}</tbody>
            </table>
            <h3>Hierarchy Levels</h3>
            <div className="tag-list">
              {auditReport.database.levels.map((level) => <span className="tag" key={level.level}>{level.label}: {level.count}</span>)}
            </div>
          </section>
          <section>
            <h3>Retrieval Benchmarks</h3>
            <div className="compare-grid">
              {auditReport.retrieval.tests.map((test) => (
                <div className="compare-card" key={test.query}>
                  <h3>{test.query}</h3>
                  {test.modes.map((mode) => (
                    <button type="button" key={mode.name}>
                      <strong>{mode.name}</strong>
                      <small>top {mode.topScore ?? "n/a"} · spread {mode.scoreSpread ?? "n/a"} · {mode.candidateCount.toLocaleString()} candidates</small>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}
