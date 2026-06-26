import React from "react";
import Plot from "react-plotly.js";

import { clusterColor } from "../lib/helpers";

export function ExploreWorkspace({ controller }) {
  return (
    <>
      <section className="chart-panel" onMouseLeave={controller.handleChartMouseLeave} onMouseUp={controller.selectHoveredPoint}>
        {controller.plotData.length ? (
          <Plot
            key={`${controller.prefs.dimensions}-${controller.selectedCollection}`}
            data={controller.plotData}
            layout={controller.plotLayout}
            revision={controller.selectionRevision}
            config={{ responsive: true, scrollZoom: true, displaylogo: false, modeBarButtonsToRemove: ["toImage"] }}
            className="plot"
            useResizeHandler
            onInitialized={controller.handlePlotReady}
            onSelected={controller.handlePlotSelected}
            onDeselect={controller.clearSelections}
            onClick={controller.handlePlotClick}
            onHover={controller.handlePlotHover}
            onUnhover={controller.handlePlotUnhover}
            onRelayout={controller.handlePlotRelayout}
          />
        ) : (
          <div className="empty-state">
            <h2>No points to display</h2>
            <p>Select a valid ChromaDB path and collection, or clear active filters.</p>
          </div>
        )}
      </section>
      <div className="hover-preview" title="Point preview">
        {controller.hoverPreview}
      </div>
      <div className="table-divider" role="separator" aria-label="Resize table height" onMouseDown={controller.startTableResize}>
        <span />
      </div>
      <section className="table-panel" style={{ height: controller.tableHeight }}>
        <button
          type="button"
          className="clear-table-selection"
          title="Clear table row and chart point selections"
          onClick={controller.clearSelections}
          disabled={!controller.tableSelectedIds.length && !controller.chartSelectedIds.length && !controller.searchActive && controller.selectedCluster === ""}
        >
          Clear
        </button>
        <table>
          <thead>
            <tr>
              <th>Cluster</th>
              <th>ID</th>
              <th>Source</th>
              <th>Title</th>
              <th>Preview</th>
            </tr>
          </thead>
          <tbody>
            {controller.visibleTableRows.map((row) => (
              <tr
                key={row.id}
                className={controller.tableSelectedSet.has(String(row.id)) ? "selected-row" : ""}
                onClick={() => {
                  controller.setInspectedRow(row);
                  const id = String(row.id);
                  controller.setTableSelectedIds((current) => (
                    current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
                  ));
                }}
              >
                <td><span className="swatch" style={{ background: clusterColor(row.cluster, controller.colorMap) }} />{row.cluster}</td>
                <td>{row.id}</td>
                <td>{row.source}</td>
                <td>{row.title}</td>
                <td>{row.preview}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
