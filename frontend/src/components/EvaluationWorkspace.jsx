import React, { useEffect, useRef, useState } from "react";

const emptyQuery = () => ({
  query: "", query_class: "factual", answerable: true, expected_speakers: [], expected_node_types: [], date_start: "", date_end: "",
  judgments: [], acceptable_evidence_sets: [], reference_claims: [], hard_negative_ids: [], provenance: "human",
  human_reviewed: true, second_reviewer: "", adjudication_state: "pending", adjudication_note: "",
});

export function EvaluationWorkspace({ controller }) {
  const [datasets, setDatasets] = useState([]);
  const [dataset, setDataset] = useState({ name: "Untitled Benchmark", corpus_fingerprint: "unknown", queries: [emptyQuery()] });
  const [selected, setSelected] = useState(0);
  const [identityPool, setIdentityPool] = useState("");
  const [stale, setStale] = useState(null);
  const [error, setError] = useState("");
  const fileRef = useRef(null);

  const refresh = () => fetch("/api/evaluation/datasets").then((r) => r.json()).then((p) => setDatasets(p.datasets || [])).catch((e) => setError(String(e)));
  useEffect(refresh, []);
  const query = dataset.queries[selected] || emptyQuery();
  const updateQuery = (changes) => setDataset((current) => ({ ...current, queries: current.queries.map((item, index) => index === selected ? { ...item, ...changes } : item) }));

  const loadDataset = async (id) => {
    const response = await fetch(`/api/evaluation/datasets/${id}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    setDataset(payload.dataset); setSelected(0); setStale(null);
  };
  const save = async () => {
    const response = await fetch("/api/evaluation/datasets", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(dataset) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    setDataset(payload.dataset); refresh();
  };
  const exportDataset = () => {
    const pack = { format: "podcast-evaluation-pack-v1", dataset };
    const blob = new Blob([JSON.stringify(pack, null, 2)], { type: "application/json" });
    const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `${dataset.name.replace(/\W+/g, "-").toLowerCase()}.json`; link.click(); URL.revokeObjectURL(link.href);
  };
  const importDataset = async (event) => {
    const file = event.target.files?.[0]; if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      if (parsed.format && parsed.format !== "podcast-evaluation-pack-v1") throw new Error(`Unsupported evaluation pack: ${parsed.format}`);
      setDataset(parsed.format === "podcast-evaluation-pack-v1" ? parsed.dataset : parsed);
      setSelected(0); setStale(null);
    } catch (reason) { setError(`Import failed: ${reason}`); }
    event.target.value = "";
  };
  const validate = async () => {
    const ids = identityPool.split(/\s+/).filter(Boolean);
    const response = await fetch("/api/evaluation/validate-identities", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ queries: dataset.queries, available_document_ids: ids, available_source_span_ids: ids }) });
    setStale(await response.json());
  };
  const safe = (action) => () => Promise.resolve(action()).catch((reason) => setError(String(reason)));

  return (
    <section className="audit-workspace evaluation-workspace">
      <div className="audit-hero"><div><h2>Evaluation Laboratory</h2><p>Author, review, validate, and port judged retrieval datasets.</p></div><div className="audit-score">{dataset.queries.length}</div></div>
      <div className="audit-actions">
        <button type="button" onClick={safe(save)}>Save Dataset</button><button type="button" onClick={exportDataset}>Export JSON</button>
        <button type="button" onClick={() => fileRef.current?.click()}>Import Evaluation Pack</button><input ref={fileRef} hidden type="file" accept=".json" onChange={importDataset} />
        <button type="button" onClick={() => controller.setWorkspaceMode("Explore")}>Open Explore</button><button type="button" onClick={() => controller.setWorkspaceMode("Audit Report")} disabled={!controller.auditReport}>Open Audit</button>
      </div>
      {error ? <p className="error-text">{error}</p> : null}
      <div className="audit-grid">
        <div className="audit-column"><section><h3>Datasets</h3><table className="mini-table"><tbody>{datasets.map((item) => <tr key={item.path} onClick={safe(() => loadDataset(item.dataset_id))}><td>{item.name || "Invalid"}</td><td>{item.queries ?? "n/a"}</td><td>{item.corpus_fingerprint || item.error}</td></tr>)}</tbody></table></section>
          <section><h3>Dataset Identity</h3><label>Name<input value={dataset.name} onChange={(e) => setDataset({ ...dataset, name: e.target.value })} /></label><label>Corpus fingerprint<input value={dataset.corpus_fingerprint} onChange={(e) => setDataset({ ...dataset, corpus_fingerprint: e.target.value })} /></label><p className="muted">Pack format: podcast-evaluation-pack-v1 · Query provenance is retained per query.</p></section>
          <section><h3>Queries</h3>{dataset.queries.map((item, index) => <button type="button" key={item.query_id || index} onClick={() => setSelected(index)}>{index + 1}. {item.query || "New query"}</button>)}<button type="button" onClick={() => { setDataset({ ...dataset, queries: [...dataset.queries, emptyQuery()] }); setSelected(dataset.queries.length); }}>Add Query</button></section>
        </div>
        <div className="audit-column"><section><h3>Judgment Editor</h3>
          <label>Query<textarea value={query.query} onChange={(e) => updateQuery({ query: e.target.value })} /></label>
          <label>Class<input value={query.query_class} onChange={(e) => updateQuery({ query_class: e.target.value })} /></label>
          <label><input type="checkbox" checked={query.answerable} onChange={(e) => updateQuery({ answerable: e.target.checked })} /> Answerable</label><label>Provenance<select value={query.provenance || "human"} onChange={(e) => updateQuery({ provenance: e.target.value, human_reviewed: e.target.value === "human" })}><option value="human">Human-authored</option><option value="generated">Generated question</option><option value="synthetic">Synthetic fixture</option></select></label>
          <label>Expected speakers (comma-separated)<input value={(query.expected_speakers || []).join(", ")} onChange={(e) => updateQuery({ expected_speakers: e.target.value.split(",").map((v) => v.trim()).filter(Boolean) })} /></label>
          <label>Evidence judgments JSON<textarea rows={8} value={JSON.stringify(query.judgments || [], null, 2)} onChange={(e) => { try { updateQuery({ judgments: JSON.parse(e.target.value) }); setError(""); } catch { setError("Judgments must remain valid JSON."); } }} /></label>
          <label>Hard negative IDs<input value={(query.hard_negative_ids || []).join(", ")} onChange={(e) => updateQuery({ hard_negative_ids: e.target.value.split(",").map((v) => v.trim()).filter(Boolean) })} /></label>
          <label>Second reviewer<input value={query.second_reviewer || ""} onChange={(e) => updateQuery({ second_reviewer: e.target.value })} /></label><label>Adjudication state<select value={query.adjudication_state || "pending"} onChange={(e) => updateQuery({ adjudication_state: e.target.value })}><option value="pending">Pending</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option><option value="disputed">Disputed</option></select></label><label>Adjudication note<textarea value={query.adjudication_note || ""} onChange={(e) => updateQuery({ adjudication_note: e.target.value })} /></label>
        </section><section><h3>Identity Validation</h3><p className="muted">Paste currently available document and source-span IDs to identify stale evidence without discarding judgments.</p><textarea value={identityPool} onChange={(e) => setIdentityPool(e.target.value)} /><button type="button" onClick={safe(validate)}>Validate IDs</button>{stale ? <pre>{JSON.stringify(stale, null, 2)}</pre> : null}</section></div>
      </div>
    </section>
  );
}
