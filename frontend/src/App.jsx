import React from "react";

import { AppOverlays } from "./components/AppOverlays";
import { AuditWorkspace } from "./components/AuditWorkspace";
import { ExploreWorkspace } from "./components/ExploreWorkspace";
import { InfoPanel } from "./components/InfoPanel";
import { Sidebar } from "./components/Sidebar";
import { useRagScopeController } from "./hooks/useRagScopeController";

function App() {
  const controller = useRagScopeController();

  return (
    <div className="app-shell">
      <style>{`
        .js-plotly-plot .hoverlayer {
          display: none !important;
          opacity: 0 !important;
          visibility: hidden !important;
          pointer-events: none;
        }
        .js-plotly-plot .hoverlayer *,
        .js-plotly-plot .hovertext,
        .js-plotly-plot .hovertext * {
          display: none !important;
          opacity: 0 !important;
          visibility: hidden !important;
        }
        .js-plotly-plot .hoverlayer:has(.hovertext) {
          display: none !important;
          opacity: 0 !important;
          visibility: hidden !important;
        }
      `}</style>
      <Sidebar controller={controller} />
      <main className="workspace" ref={controller.mainRef}>
        <div className="work-main">
          <header className="toolbar">
            <div>
              <strong className="db-title">
                {controller.selectedCollection || "No collection selected"}
                {(controller.loading || controller.pathChecking) && <span className="spinner" aria-label="Backend processing" />}
              </strong>
              <span>
                {controller.tableFilteredRows.length.toLocaleString()} table rows, {controller.searchResultRows.length.toLocaleString()} search results of {controller.sourceRows.length.toLocaleString()} chunks
              </span>
            </div>
            <div className="toolbar-actions">
              {controller.loading && <span className="loading">Loading...</span>}
              {controller.error && (
                <button
                  type="button"
                  className="error-text"
                  title="Click to view and copy the full message"
                  onClick={() => controller.setMessageModal({ title: "Message", text: controller.error })}
                >
                  {controller.short(controller.error, 160)}
                </button>
              )}
            </div>
          </header>
          <div className="pipeline-ribbon">
            <span><strong>{controller.pipelineSummary.loaded.toLocaleString()}</strong> loaded</span>
            <span><strong>{controller.pipelineSummary.visible.toLocaleString()}</strong> visible</span>
            <span><strong>{controller.pipelineSummary.clusters.toLocaleString()}</strong> clusters</span>
            <span><strong>{controller.pipelineSummary.levels.toLocaleString()}</strong> levels</span>
            <span><strong>{controller.pipelineSummary.speakers.toLocaleString()}</strong> speakers</span>
            <span className={controller.pipelineSummary.ranked ? "hot" : ""}><strong>{controller.pipelineSummary.ranked.toLocaleString()}</strong> ranked</span>
            <span className={controller.pipelineSummary.orphans ? "warn" : ""}><strong>{controller.pipelineSummary.orphans.toLocaleString()}</strong> orphans</span>
          </div>
          <div className="workspace-switch">
            {["Explore", "Audit Report"].map((mode) => (
              <button
                type="button"
                key={mode}
                className={controller.workspaceMode === mode ? "active" : ""}
                onClick={() => controller.setWorkspaceMode(mode)}
                disabled={mode === "Audit Report" && !controller.auditReport}
              >
                {mode}
              </button>
            ))}
          </div>
          {controller.workspaceMode === "Explore" ? (
            <ExploreWorkspace controller={controller} />
          ) : (
            <AuditWorkspace controller={controller} />
          )}
        </div>

        <div className="right-resizer" role="separator" aria-label="Resize right information panel" onMouseDown={controller.startRightResize} />
        <InfoPanel controller={controller} />
      </main>
      <AppOverlays controller={controller} />
    </div>
  );
}

export default App;
