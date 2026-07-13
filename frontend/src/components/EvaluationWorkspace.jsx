import React, { useEffect, useState } from "react";

export function EvaluationWorkspace({ controller }) {
  const [datasets, setDatasets] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/evaluation/datasets")
      .then((response) => response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`)))
      .then((payload) => setDatasets(payload.datasets || []))
      .catch((reason) => setError(String(reason)));
  }, []);

  return (
    <section className="audit-workspace evaluation-workspace">
      <div className="audit-hero">
        <div>
          <h2>Evaluation Laboratory</h2>
          <p>Versioned judged queries, deterministic metrics, paired comparisons, and promotion guardrails.</p>
        </div>
        <div className="audit-score">{datasets.length}</div>
      </div>
      <div className="audit-actions">
        <button type="button" onClick={() => controller.setWorkspaceMode("Explore")}>Link Explore Selection</button>
        <button type="button" onClick={() => controller.setWorkspaceMode("Audit Report")} disabled={!controller.auditReport}>Open Audit</button>
      </div>
      {error ? <p className="error-text">{error}</p> : null}
      <div className="audit-grid">
        <div className="audit-column">
          <section>
            <h3>Judged Datasets</h3>
            <p className="muted">Grades: 0 irrelevant, 1 related, 2 relevant/derived, 3 primary evidence.</p>
            <table className="mini-table">
              <tbody>{datasets.map((item) => (
                <tr key={item.path}><td>{item.name || "Invalid dataset"}</td><td>{item.queries ?? "n/a"} queries</td><td>{item.corpus_fingerprint || item.error}</td></tr>
              ))}</tbody>
            </table>
          </section>
        </div>
        <div className="audit-column">
          <section>
            <h3>Promotion Scorecard</h3>
            <dl className="audit-dl">
              <dt>Primary</dt><dd>nDCG@10</dd>
              <dt>Recall guardrail</dt><dd>Recall@20</dd>
              <dt>Hard filters</dt><dd>100%</dd>
              <dt>Latency</dt><dd>≤ 25% regression</dd>
              <dt>Statistics</dt><dd>10k paired bootstrap · 95% CI</dd>
            </dl>
          </section>
          <section>
            <h3>Authoring Workflow</h3>
            <p>Create local datasets through the evaluation API, retain document and source-span identities, and require human review before synthetic questions count toward promotion.</p>
          </section>
        </div>
      </div>
    </section>
  );
}
