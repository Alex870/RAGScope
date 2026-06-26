import React from "react";

function SearchSection({ controller }) {
  return (
    <>
      <label>
        Text search
        <input
          value={controller.prefs.textSearch}
          onChange={(event) => {
            controller.updatePref("textSearch", event.target.value);
            controller.setHighlightedIds([]);
            controller.setAnalysisResult(null);
          }}
          placeholder="Filter visible chunks"
        />
      </label>
      <label>
        Semantic search
        <textarea
          value={controller.prefs.semanticSearch}
          onChange={(event) => {
            controller.updatePref("semanticSearch", event.target.value);
            controller.setAnalysisResult(null);
          }}
          placeholder="Find nearest chunks by meaning"
        />
      </label>
      <label>
        Top K
        <input type="number" min="1" max="100" value={controller.prefs.semanticTopK} onChange={(event) => controller.updatePref("semanticTopK", Number(event.target.value))} />
      </label>
      <button type="button" className="primary" onClick={controller.handleSemanticSearch} disabled={!controller.prefs.semanticSearch.trim() || !controller.selectedCollection || controller.semanticLoading}>
        {controller.semanticLoading && <span className="button-spinner" aria-hidden="true" />}
        {controller.semanticLoading ? "Searching..." : "Run Semantic Search"}
      </button>
      <button type="button" onClick={controller.handleRetrievalExperiment} disabled={!controller.prefs.semanticSearch.trim() || !controller.selectedCollection || controller.retrievalLoading}>
        {controller.retrievalLoading && <span className="button-spinner" aria-hidden="true" />}
        {controller.retrievalLoading ? "Scoring..." : "Experiment: Score Results"}
      </button>
      <button type="button" onClick={controller.compareRetrievalModes} disabled={!controller.prefs.semanticSearch.trim() || !controller.selectedCollection || controller.compareLoading}>
        {controller.compareLoading && <span className="button-spinner" aria-hidden="true" />}
        {controller.compareLoading ? "Comparing..." : "Compare Retrieval Modes"}
      </button>
      <button type="button" onClick={controller.clearSelections}>Clear Selection</button>
      {!!controller.hierarchyOptions.length && (
        <div className="hierarchy-filter">
          <div className="filter-heading">Hierarchy Levels</div>
          {controller.hierarchyOptions.map((option) => (
            <label className="check hierarchy-check" key={option.level}>
              <input
                type="checkbox"
                checked={controller.selectedHierarchyLevels.has(option.level)}
                onChange={(event) => {
                  const next = new Set(controller.selectedHierarchyLevels);
                  if (event.target.checked) {
                    next.add(option.level);
                  } else {
                    next.delete(option.level);
                  }
                  const allSelected = controller.hierarchyOptions.every((item) => next.has(item.level));
                  controller.updatePref("hierarchyLevels", allSelected ? null : [...next]);
                  controller.setHighlightedIds([]);
                  controller.setAnalysisResult(null);
                }}
              />
              <span>{option.label}</span>
              <span className="count">{option.count.toLocaleString()}</span>
            </label>
          ))}
        </div>
      )}
    </>
  );
}

function AuditSection({ controller }) {
  return (
    <>
      <label>
        Audit preset
        <select value={controller.auditPreset} onChange={(event) => controller.setAuditPreset(event.target.value)}>
          <option>Quick Scan</option>
          <option>Standard Audit</option>
          <option>Retrieval Benchmark</option>
          <option>Metadata / Hierarchy Only</option>
        </select>
      </label>
      <label>
        Scope
        <select value={controller.auditScope} onChange={(event) => controller.setAuditScope(event.target.value)}>
          <option>Loaded Collection</option>
          <option>Current Filters</option>
        </select>
      </label>
      <label>
        Seed queries
        <textarea value={controller.auditQueries} onChange={(event) => controller.setAuditQueries(event.target.value)} />
      </label>
      <div className="button-row">
        <button
          type="button"
          className="tiny-button"
          title="Ask the configured LLM to generate a reviewable batch of audit seed queries from loaded corpus samples."
          onClick={controller.generateAuditQueries}
          disabled={controller.llmAuditSettings.provider === "Disabled" || controller.queryGenerationLoading || !controller.sourceRows.length}
        >
          {controller.queryGenerationLoading && <span className="button-spinner" aria-hidden="true" />}
          {controller.queryGenerationLoading ? "Generating..." : "Generate"}
        </button>
        <button type="button" className="tiny-button" title="Save the current audit query batch as portable JSON for repeatable testing." onClick={controller.exportAuditQueries}>Save</button>
        <button type="button" className="tiny-button" title="Load a previously saved audit query JSON batch so the same test can be rerun." onClick={() => controller.queryImportRef.current?.click()}>Load</button>
      </div>
      <input ref={controller.queryImportRef} type="file" accept="application/json,.json" className="hidden-file" onChange={controller.importAuditQueries} />
      <label>
        LLM provider
        <select value={controller.llmAuditSettings.provider} onChange={(event) => controller.updateLlmAuditSetting("provider", event.target.value)}>
          <option>Disabled</option>
          <option>LM Studio</option>
          <option>OpenAI-compatible URL</option>
        </select>
      </label>
      {controller.llmAuditSettings.provider !== "Disabled" && (
        <>
          <label>
            OpenAI-compatible base URL
            <input
              value={controller.llmAuditSettings.baseUrl}
              onChange={(event) => controller.updateLlmAuditSetting("baseUrl", event.target.value)}
              onBlur={controller.refreshLlmModels}
              placeholder="http://127.0.0.1:1234/v1"
            />
          </label>
          <label>
            Model
            <div className="model-row">
              <input
                list="llm-model-options"
                value={controller.llmAuditSettings.model}
                onChange={(event) => controller.updateLlmAuditSetting("model", event.target.value)}
                placeholder="Select or type a model name"
              />
              <button type="button" className="icon-button" onClick={controller.refreshLlmModels} disabled={controller.llmModelsLoading || !controller.llmAuditSettings.baseUrl.trim()} title="Refresh available models">
                {controller.llmModelsLoading ? "..." : "↻"}
              </button>
            </div>
            <datalist id="llm-model-options">
              {controller.llmModelNames.map((name) => <option value={name} key={name} />)}
            </datalist>
            <small>
              {controller.llmModelDetails[controller.llmAuditSettings.model]?.context_length
                ? `Reported context: ${controller.llmModelDetails[controller.llmAuditSettings.model].context_length.toLocaleString()} tokens`
                : "Reported context: unknown"}
            </small>
          </label>
          <label>
            API key
            <input type="password" value={controller.llmAuditSettings.apiKey} onChange={(event) => controller.updateLlmAuditSetting("apiKey", event.target.value)} placeholder="Optional for LM Studio" />
          </label>
          <label className="check">
            <input type="checkbox" checked={controller.llmAuditSettings.limitContext} onChange={(event) => controller.updateLlmAuditSetting("limitContext", event.target.checked)} />
            Limit LLM context to metadata/previews/retrieval summaries
          </label>
        </>
      )}
      <button type="button" className="primary" onClick={controller.runAudit} disabled={!controller.sourceRows.length || !controller.selectedCollection || controller.auditLoading}>
        {controller.auditLoading && <span className="button-spinner" aria-hidden="true" />}
        {controller.auditLoading ? "Running Audit..." : "Run RAG Quality Audit"}
      </button>
      <button type="button" onClick={() => controller.setWorkspaceMode("Audit Report")} disabled={!controller.auditReport}>Show Audit Report</button>
      <div className="saved-list">
        {controller.savedAudits.slice(0, 5).map((report) => (
          <div className="saved-item" key={report.id}>
            <button type="button" onClick={() => {
              controller.setAuditReport(report);
              controller.setWorkspaceMode("Audit Report");
            }}>
              {report.collection} · {report.scores?.overall ?? "n/a"}
            </button>
            <button type="button" className="danger" onClick={() => controller.setSavedAudits((current) => current.filter((item) => item.id !== report.id))}>Delete</button>
          </div>
        ))}
      </div>
    </>
  );
}

function ViewSection({ controller }) {
  return (
    <>
      <label>
        Dimensions
        <select value={controller.prefs.dimensions} onChange={(event) => controller.updatePref("dimensions", Number(event.target.value))}>
          <option value={2}>2D</option>
          <option value={3}>3D</option>
        </select>
      </label>
      <label>
        Reduction
        <select value={controller.prefs.reductionMethod} onChange={(event) => controller.updatePref("reductionMethod", event.target.value)}>
          <option>UMAP</option>
          <option>PCA</option>
        </select>
      </label>
      <label>
        Clustering
        <select value={controller.prefs.clusteringMethod} onChange={(event) => controller.updatePref("clusteringMethod", event.target.value)}>
          <option>Auto</option>
          <option>HDBSCAN</option>
          <option>KMeans</option>
          <option>None</option>
        </select>
      </label>
      <label>
        KMeans clusters
        <input type="number" min="2" max="80" value={controller.prefs.clusterCount} onChange={(event) => controller.updatePref("clusterCount", Number(event.target.value))} />
      </label>
      <label>
        HDBSCAN min size
        <input type="number" min="2" max="100" value={controller.prefs.minClusterSize} onChange={(event) => controller.updatePref("minClusterSize", Number(event.target.value))} />
      </label>
      <label>
        Popup Delay
        <input type="number" min="0" max="5" step="0.1" value={controller.prefs.popupDelay} onChange={(event) => controller.updatePref("popupDelay", Number(event.target.value))} />
      </label>
      <label className="check">
        <input type="checkbox" checked={controller.prefs.hoverEnabled} onChange={(event) => controller.updatePref("hoverEnabled", event.target.checked)} />
        Enable point popups
      </label>
      <button type="button" className="primary" onClick={controller.loadDataset} disabled={!controller.selectedCollection || !controller.pathValid || controller.loading}>Recompute View</button>
    </>
  );
}

function SavedSection({ controller }) {
  return (
    <>
      <label>
        View name
        <input value={controller.viewName} onChange={(event) => controller.setViewName(event.target.value)} placeholder="Investigation name" />
      </label>
      <label>
        Description
        <textarea value={controller.viewDescription} onChange={(event) => controller.setViewDescription(event.target.value)} placeholder="What this view captures" />
      </label>
      <button type="button" className="primary" onClick={controller.saveView} disabled={!controller.viewName.trim()}>Save Current View</button>
      <div className="saved-list">
        {controller.savedViews.map((view) => (
          <div className="saved-item" key={view.filename}>
            <button
              type="button"
              title="Left-click to load. Right-click to rename."
              onClick={() => controller.applySavedView(view)}
              onContextMenu={(event) => {
                event.preventDefault();
                controller.renameView(view);
              }}
            >
              {view.name || view.filename}
            </button>
            <button type="button" className="danger" onClick={() => controller.deleteView(view.filename)}>Delete</button>
          </div>
        ))}
      </div>
    </>
  );
}

function ChromaDbSection({ controller }) {
  return (
    <div className={controller.hasInvalidPath ? "path-warning" : ""}>
      <label>
        ChromaDB Path
        <div className="path-row">
          <input
            value={controller.chromaPath}
            onChange={(event) => controller.setChromaPath(event.target.value)}
            onBlur={controller.refreshCollections}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.currentTarget.blur();
                controller.refreshCollections();
              }
            }}
          />
          <button type="button" className="icon-button" title="Browse for a local ChromaDB folder" onClick={controller.browseForFolder}>...</button>
        </div>
      </label>
      <div className={`path-status ${controller.pathValid ? "ok" : "bad"}`}>
        {controller.pathChecking ? "Checking path..." : controller.pathMessage || (controller.pathValid ? "Path is valid" : "Path has not been validated")}
      </div>
      <button type="button" className="primary" onClick={controller.refreshCollections}>Refresh Collections</button>
      <label>
        Collection
        <select value={controller.selectedCollection} onChange={(event) => controller.setSelectedCollection(event.target.value)} disabled={!controller.collections.length}>
          {controller.collections.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
      </label>
      <label>
        Max load
        <input type="number" min="100" max="100000" step="100" value={controller.prefs.maxLoad} onChange={(event) => controller.updatePref("maxLoad", Number(event.target.value))} />
      </label>
      <label className="check">
        <input type="checkbox" checked={controller.prefs.sampling} onChange={(event) => controller.updatePref("sampling", event.target.checked)} />
        Sample large collections
      </label>
    </div>
  );
}

export function Sidebar({ controller }) {
  // The sidebar is organized by investigation workflow rather than by raw settings
  // so reviewers can trace how search, audit, view tuning, and persistence fit together.
  const sections = {
    Search: <SearchSection controller={controller} />,
    Audit: <AuditSection controller={controller} />,
    View: <ViewSection controller={controller} />,
    Saved: <SavedSection controller={controller} />,
    ChromaDB: <ChromaDbSection controller={controller} />,
  };

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">RS</div>
        <div>
          <h1>RAGScope</h1>
          <span>RAG quality workbench</span>
        </div>
      </div>

      {Object.entries(sections).map(([section, content]) => (
        <section className={`accordion ${controller.activeSection === section ? "open" : ""}`} key={section}>
          <button type="button" className="accordion-title" onClick={() => controller.setActiveSection(section)}>
            <span>{section}</span>
            <span>{controller.activeSection === section ? "−" : "+"}</span>
          </button>
          {controller.activeSection === section && <div className="accordion-body">{content}</div>}
        </section>
      ))}

      <button
        ref={controller.chartWakeButtonRef}
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        className={controller.chartWakeButtonVisible ? "chart-wake-button armed" : "chart-wake-button"}
        data-chart-wake-pulse={controller.chartWakePulse}
        onClick={controller.handleChartWakeClick}
      >
        Wake chart
      </button>
    </aside>
  );
}
