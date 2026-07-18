import React, { useEffect, useState } from "react";

const STATES = ["draft", "validating", "ready", "running", "review_required", "decided", "archived"];

export function CampaignWorkspace() {
  const [campaigns, setCampaigns] = useState([]);
  const [selected, setSelected] = useState(null);
  const [packPath, setPackPath] = useState("");
  const [readiness, setReadiness] = useState(null);
  const [error, setError] = useState("");
  const refresh = () => fetch("/api/evaluation/campaigns").then((r) => r.json()).then((p) => setCampaigns(p.campaigns || [])).catch((e) => setError(String(e)));
  useEffect(refresh, []);
  const request = async (url, options = {}) => {
    const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    return payload;
  };
  const importPack = async () => { setReadiness(await request("/api/evaluation/campaigns/import-pack", { method: "POST", body: JSON.stringify({ path: packPath }) })); };
  const transition = async (state) => { const value = await request(`/api/evaluation/campaigns/${selected.campaign_id}/transition/${state}`, { method: "POST" }); setSelected(value.campaign); refresh(); };
  const exportReport = async () => {
    const value = await request("/api/evaluation/campaigns/export", { method: "POST", body: JSON.stringify({ campaign: selected }) });
    const blob = new Blob([JSON.stringify(value.campaign, null, 2)], { type: "application/json" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "campaign-report.json"; link.click(); URL.revokeObjectURL(link.href);
  };
  const safe = (fn) => () => Promise.resolve(fn()).catch((e) => setError(String(e)));
  const next = selected ? STATES[STATES.indexOf(selected.state) + 1] : null;
  return <section><h3>Evaluation Campaigns</h3><p className="muted">One-podcast readiness, aligned runs, stale review, and human promotion.</p>
    <label>Selected local pack path<input value={packPath} onChange={(e) => setPackPath(e.target.value)} /></label><button type="button" onClick={safe(importPack)}>Import and validate</button>
    {readiness ? <div className="readiness-cards"><strong>{readiness.readiness.ready ? "Ready" : "Blocked"}</strong> · {readiness.readiness.episode_count} episodes · {readiness.readiness.reviewed_count}/{readiness.readiness.query_count} reviewed</div> : null}
    {error ? <p className="error-text">{error}</p> : null}
    <table className="mini-table"><thead><tr><th>Pack</th><th>State</th><th>Runs</th><th>Stale</th></tr></thead><tbody>{campaigns.map((item) => <tr key={item.campaign_id} onClick={() => setSelected(item)}><td>{item.pack_id}</td><td>{item.state}</td><td>{item.run_ids?.length || 0}</td><td>{item.stale_judgment_ids?.length || 0}</td></tr>)}</tbody></table>
    {selected ? <div><h4>Baseline / candidate matrix</h4><pre>{JSON.stringify({ baseline: selected.baseline_release_id, candidate: selected.candidate_release_id, runs: selected.run_ids, releaseCritical: selected.gates?.release_critical_query_ids || [], regressions: selected.results?.regressions || [], staleJudgments: selected.stale_judgment_ids || [] }, null, 2)}</pre>{next ? <button type="button" onClick={safe(() => transition(next))}>Advance to {next}</button> : null}<button type="button" onClick={safe(exportReport)}>Export portable report</button></div> : null}
  </section>;
}
