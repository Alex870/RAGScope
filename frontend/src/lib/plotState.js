export function mergeAxisView(existingAxis = {}, update = {}) {
  return { ...existingAxis, ...update };
}

export function normalizePlotlyRelayout(event = {}, dimensions = 2) {
  const view = {};
  if (dimensions === 3) {
    if (event["scene.camera"]) {
      view.scene = { ...(view.scene || {}), camera: event["scene.camera"] };
    }
    if (event.scene?.camera) {
      view.scene = { ...(view.scene || {}), camera: event.scene.camera };
    }
    return view;
  }

  const xaxis = {};
  const yaxis = {};
  if (event["xaxis.range[0]"] !== undefined && event["xaxis.range[1]"] !== undefined) {
    xaxis.range = [event["xaxis.range[0]"], event["xaxis.range[1]"]];
    xaxis.autorange = false;
  }
  if (event["yaxis.range[0]"] !== undefined && event["yaxis.range[1]"] !== undefined) {
    yaxis.range = [event["yaxis.range[0]"], event["yaxis.range[1]"]];
    yaxis.autorange = false;
  }
  if (event["xaxis.autorange"] !== undefined) {
    xaxis.autorange = event["xaxis.autorange"];
    if (event["xaxis.autorange"]) delete xaxis.range;
  }
  if (event["yaxis.autorange"] !== undefined) {
    yaxis.autorange = event["yaxis.autorange"];
    if (event["yaxis.autorange"]) delete yaxis.range;
  }
  if (event.xaxis?.range) {
    xaxis.range = event.xaxis.range;
    xaxis.autorange = false;
  }
  if (event.yaxis?.range) {
    yaxis.range = event.yaxis.range;
    yaxis.autorange = false;
  }
  if (Object.keys(xaxis).length) view.xaxis = xaxis;
  if (Object.keys(yaxis).length) view.yaxis = yaxis;
  return view;
}

export function mergePlotView(existing = {}, update = {}) {
  const merged = { ...existing, ...update };
  if (update.xaxis) merged.xaxis = mergeAxisView(existing.xaxis, update.xaxis);
  if (update.yaxis) merged.yaxis = mergeAxisView(existing.yaxis, update.yaxis);
  if (update.scene) merged.scene = { ...(existing.scene || {}), ...update.scene };
  return merged;
}

export function normalizeStoredPlotView(view = {}, dimensions = 2) {
  return mergePlotView(view, normalizePlotlyRelayout(view, dimensions));
}

