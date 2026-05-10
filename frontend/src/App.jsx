import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Plot from "react-plotly.js";
import {
  API_BASE,
  DEFAULT_AUDIT_QUERIES,
  DEFAULT_LLM_AUDIT_SETTINGS,
  DEFAULT_PREFS,
  INFO_TABS,
  LLM_AUDIT_SETTINGS_KEY,
  MAX_ANALYSIS_IDS,
  PATH_KEY,
  RIGHT_WIDTH_KEY,
  RUNTIME_CONFIG,
  SAVED_AUDITS_KEY,
  SAVED_RUNS_KEY,
  TABLE_HEIGHT_KEY,
  VIEW_PREFS_KEY,
} from "./lib/constants";
import {
  clusterColor,
  downloadText,
  hierarchyLabel,
  hierarchyLevel,
  hierarchyRank,
  keywordTokens,
  loadJson,
  numericMeta,
  percent,
  retrievalRankColor,
  rowNodeId,
  rowParentId,
  scoreFromPercent,
  short,
  splitSpeakerValues,
} from "./lib/helpers";
import { mergePlotView, normalizePlotlyRelayout, normalizeStoredPlotView } from "./lib/plotState";

function App() {
  const [activeSection, setActiveSection] = useState("Search");
  const [workspaceMode, setWorkspaceMode] = useState("Explore");
  const [chromaPath, setChromaPath] = useState(() => RUNTIME_CONFIG.defaultChromaPath || localStorage.getItem(PATH_KEY) || "./chroma");
  const [pathValid, setPathValid] = useState(false);
  const [pathMessage, setPathMessage] = useState("");
  const [pathChecking, setPathChecking] = useState(false);
  const [collections, setCollections] = useState([]);
  const [selectedCollection, setSelectedCollection] = useState("");
  const [prefs, setPrefs] = useState(() => ({ ...DEFAULT_PREFS, ...loadJson(VIEW_PREFS_KEY, {}) }));
  const [dataset, setDataset] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [messageModal, setMessageModal] = useState(null);
  const [toasts, setToasts] = useState([]);
  const [chartSelectedIds, setChartSelectedIds] = useState([]);
  const [tableSelectedIds, setTableSelectedIds] = useState([]);
  const [highlightedIds, setHighlightedIds] = useState([]);
  const [selectedCluster, setSelectedCluster] = useState("");
  const [inspectedRow, setInspectedRow] = useState(null);
  const [inspectedDocument, setInspectedDocument] = useState(null);
  const [inspectorLoading, setInspectorLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [infoTab, setInfoTab] = useState("Inspect");
  const [retrievalLoading, setRetrievalLoading] = useState(false);
  const [retrievalResult, setRetrievalResult] = useState(null);
  const [retrievalNotes, setRetrievalNotes] = useState("");
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareResult, setCompareResult] = useState(null);
  const [hoverPreview, setHoverPreview] = useState("");
  const [savedViews, setSavedViews] = useState([]);
  const [savedRuns, setSavedRuns] = useState(() => loadJson(SAVED_RUNS_KEY, []));
  const [savedAudits, setSavedAudits] = useState(() => loadJson(SAVED_AUDITS_KEY, []));
  const [auditReport, setAuditReport] = useState(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditPreset, setAuditPreset] = useState("Standard Audit");
  const [auditScope, setAuditScope] = useState("Loaded Collection");
  const [auditQueries, setAuditQueries] = useState(DEFAULT_AUDIT_QUERIES.join("\n"));
  const [llmAuditSettings, setLlmAuditSettings] = useState(() => ({ ...DEFAULT_LLM_AUDIT_SETTINGS, ...loadJson(LLM_AUDIT_SETTINGS_KEY, {}) }));
  const [queryGenerationLoading, setQueryGenerationLoading] = useState(false);
  const [llmModelNames, setLlmModelNames] = useState([]);
  const [llmModelDetails, setLlmModelDetails] = useState({});
  const [llmModelsLoading, setLlmModelsLoading] = useState(false);
  const [viewName, setViewName] = useState("");
  const [viewDescription, setViewDescription] = useState("");
  const [tableHeight, setTableHeight] = useState(() => Number(localStorage.getItem(TABLE_HEIGHT_KEY) || 320));
  const [rightWidth, setRightWidth] = useState(() => Number(localStorage.getItem(RIGHT_WIDTH_KEY) || 360));
  const [plotRelayout, setPlotRelayout] = useState({});
  const [plotViewsByDimension, setPlotViewsByDimension] = useState({});
  const [selectionRevision, setSelectionRevision] = useState(0);
  const [chartWakePulse, setChartWakePulse] = useState(0);
  const [chartWakeButtonVisible, setChartWakeButtonVisible] = useState(false);
  const [dragMode, setDragMode] = useState("pan");
  const plotRelayoutRef = useRef(plotRelayout);
  const plotViewsByDimensionRef = useRef(plotViewsByDimension);
  const hoveredPointRef = useRef(null);
  const lastPlotClickRef = useRef(0);
  const chartWakeButtonRef = useRef(null);
  const chartWakeTimerRef = useRef(null);
  const hoverResetTimerRef = useRef(null);
  const mainRef = useRef(null);
  const queryImportRef = useRef(null);

  const dismissToast = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const addToast = useCallback((toast) => {
    const id = toast.id || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const nextToast = {
      id,
      type: toast.type || "info",
      title: toast.title || "Notice",
      message: toast.message || "",
      autoClose: toast.autoClose ?? !["error", "warning"].includes(toast.type),
    };
    setToasts((current) => [nextToast, ...current.filter((item) => item.id !== id)].slice(0, 5));
    if (nextToast.autoClose) {
      window.setTimeout(() => dismissToast(id), toast.duration || 4500);
    }
  }, [dismissToast]);

  useEffect(() => {
    localStorage.setItem(PATH_KEY, chromaPath);
  }, [chromaPath]);

  useEffect(() => {
    if (error) {
      addToast({ id: "latest-error", type: "error", title: "Error", message: error, autoClose: false });
    }
  }, [addToast, error]);

  useEffect(() => {
    localStorage.setItem(VIEW_PREFS_KEY, JSON.stringify(prefs));
  }, [prefs]);

  useEffect(() => {
    localStorage.setItem(SAVED_RUNS_KEY, JSON.stringify(savedRuns.slice(0, 50)));
  }, [savedRuns]);

  useEffect(() => {
    localStorage.setItem(SAVED_AUDITS_KEY, JSON.stringify(savedAudits.slice(0, 20)));
  }, [savedAudits]);

  useEffect(() => {
    localStorage.setItem(LLM_AUDIT_SETTINGS_KEY, JSON.stringify({ ...llmAuditSettings, apiKey: "" }));
  }, [llmAuditSettings]);

  useEffect(() => {
    const id = "llm-context-warning";
    const selectedContext = llmModelDetails[llmAuditSettings.model]?.context_length;
    if (llmAuditSettings.provider !== "Disabled" && !llmAuditSettings.limitContext && selectedContext && selectedContext < 8192) {
      addToast({
        id,
        type: "warning",
        title: "LLM Context Warning",
        message: `The selected model reports a ${selectedContext.toLocaleString()} token context window. Full chunk text may need aggressive trimming and can weaken audit interpretation. Enable the Limit setting or load the model with a larger context window.`,
        autoClose: false,
      });
    } else {
      dismissToast(id);
    }
  }, [addToast, dismissToast, llmAuditSettings.limitContext, llmAuditSettings.model, llmAuditSettings.provider, llmModelDetails]);

  useEffect(() => {
    localStorage.setItem(TABLE_HEIGHT_KEY, String(tableHeight));
  }, [tableHeight]);

  useEffect(() => {
    localStorage.setItem(RIGHT_WIDTH_KEY, String(rightWidth));
  }, [rightWidth]);

  useEffect(() => {
    plotViewsByDimensionRef.current = plotViewsByDimension;
  }, [plotViewsByDimension]);

  useEffect(() => {
    return () => {
      if (hoverResetTimerRef.current) window.clearTimeout(hoverResetTimerRef.current);
      if (chartWakeTimerRef.current) window.clearTimeout(chartWakeTimerRef.current);
    };
  }, []);

  const updatePref = useCallback((key, value) => {
    setPrefs((current) => ({ ...current, [key]: value }));
  }, []);

  const callApi = useCallback(async (path, options = {}) => {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || response.statusText);
    }
    return response.json();
  }, []);

  const readableError = (err) => {
    const text = err?.message || String(err);
    try {
      const parsed = JSON.parse(text);
      return parsed.detail || text;
    } catch {
      return text;
    }
  };

  const refreshCollections = useCallback(async () => {
    setError("");
    setPathChecking(true);
    try {
      const result = await callApi("/api/collections", {
        method: "POST",
        body: JSON.stringify({ chroma_path: chromaPath }),
      });
      setPathValid(Boolean(result.valid));
      setPathMessage(result.warning || result.message || "");
      setCollections(result.collections || []);
      if (result.valid || result.collections?.length) {
        dismissToast("latest-error");
      }
      if (result.resolved_path && result.resolved_path !== chromaPath) {
        setChromaPath(result.resolved_path);
      }
      if (!result.valid) {
        setActiveSection("ChromaDB");
      } else if (!selectedCollection && result.collections?.length) {
        setSelectedCollection(result.collections[0]);
      } else if (selectedCollection && result.collections?.length && !result.collections.includes(selectedCollection)) {
        setSelectedCollection(result.collections[0]);
      }
    } catch (err) {
      setPathValid(false);
      const message = readableError(err);
      setPathMessage(message);
      setCollections([]);
      setError(`Unable to inspect ChromaDB path: ${message}`);
      setActiveSection("ChromaDB");
    } finally {
      setPathChecking(false);
    }
  }, [callApi, chromaPath, dismissToast, selectedCollection]);

  useEffect(() => {
    refreshCollections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setPathValid(false);
    setPathMessage("Checking path...");
    const timer = window.setTimeout(() => {
      refreshCollections();
    }, 800);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chromaPath]);

  const loadDataset = useCallback(async () => {
    if (!selectedCollection || !pathValid) return;
    setLoading(true);
    setError("");
    try {
      const result = await callApi("/api/dataset", {
        method: "POST",
        body: JSON.stringify({
          chroma_path: chromaPath,
          collection_name: selectedCollection,
          max_load_size: prefs.maxLoad,
          chart_view: prefs.dimensions === 3 ? "3D" : "2D",
          reduction: {
            method: prefs.reductionMethod,
            n_neighbors: 15,
            min_dist: 0.1,
            use_sampling: prefs.sampling,
            sample_size: prefs.maxLoad,
          },
          clustering: {
            method: prefs.clusteringMethod,
            kmeans_clusters: prefs.clusterCount,
            hdbscan_min_cluster_size: prefs.minClusterSize,
          },
        }),
      });
      setDataset(result);
      setChartSelectedIds([]);
      setTableSelectedIds([]);
      setHighlightedIds([]);
      setInspectedRow(null);
      setRetrievalResult(null);
      setCompareResult(null);
      setDragMode("pan");
    } catch (err) {
      setDataset(null);
      setError(`Unable to load collection: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [callApi, chromaPath, pathValid, prefs, selectedCollection]);

  useEffect(() => {
    loadDataset();
  }, [loadDataset]);

  useEffect(() => {
    if (!inspectedRow?.id || !selectedCollection || !pathValid) {
      setInspectedDocument(null);
      return;
    }
    let cancelled = false;
    setInspectorLoading(true);
    callApi("/api/document", {
      method: "POST",
      body: JSON.stringify({
        chroma_path: chromaPath,
        collection_name: selectedCollection,
        id: inspectedRow.id,
      }),
    })
      .then((result) => {
        if (!cancelled) setInspectedDocument(result);
      })
      .catch(() => {
        if (!cancelled) setInspectedDocument(null);
      })
      .finally(() => {
        if (!cancelled) setInspectorLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [callApi, chromaPath, inspectedRow, pathValid, selectedCollection]);

  const sourceRows = dataset?.rows || [];
  const hierarchyOptions = useMemo(() => {
    const counts = new Map();
    sourceRows.forEach((row) => {
      const level = hierarchyLevel(row);
      counts.set(level, (counts.get(level) || 0) + 1);
    });
    return [...counts.entries()]
      .map(([level, count]) => ({
        level,
        count,
        label: hierarchyLabel(level),
        rank: hierarchyRank(level),
      }))
      .sort((left, right) => left.rank - right.rank || left.label.localeCompare(right.label));
  }, [sourceRows]);

  const selectedHierarchyLevels = useMemo(() => {
    if (Array.isArray(prefs.hierarchyLevels)) return new Set(prefs.hierarchyLevels.map(String));
    return new Set(hierarchyOptions.map((option) => option.level));
  }, [hierarchyOptions, prefs.hierarchyLevels]);

  const hierarchyFilteredRows = useMemo(() => {
    if (!hierarchyOptions.length) return sourceRows;
    return sourceRows.filter((row) => selectedHierarchyLevels.has(hierarchyLevel(row)));
  }, [hierarchyOptions.length, selectedHierarchyLevels, sourceRows]);

  const textFilteredRows = useMemo(() => {
    let rows = hierarchyFilteredRows;
    const term = prefs.textSearch.trim().toLowerCase();
    if (term) {
      rows = rows.filter((row) => {
        const haystack = `${row.id || ""} ${row.source || ""} ${row.title || ""} ${row.preview || ""}`.toLowerCase();
        return haystack.includes(term);
      });
    }
    if (selectedCluster !== "") {
      rows = rows.filter((row) => String(row.cluster) === String(selectedCluster));
    }
    return rows;
  }, [hierarchyFilteredRows, prefs.textSearch, selectedCluster]);

  const highlightedSet = useMemo(() => new Set(highlightedIds.map(String)), [highlightedIds]);
  const searchActive = Boolean(prefs.textSearch.trim() || highlightedIds.length);
  const searchResultRows = useMemo(() => {
    if (highlightedIds.length) {
      return textFilteredRows.filter((row) => highlightedSet.has(String(row.id)));
    }
    return textFilteredRows;
  }, [highlightedIds.length, highlightedSet, textFilteredRows]);
  const searchResultSet = useMemo(() => new Set(searchResultRows.map((row) => String(row.id))), [searchResultRows]);

  const tableFilteredRows = useMemo(() => {
    if (chartSelectedIds.length) {
      const selected = new Set(chartSelectedIds.map(String));
      return searchResultRows.filter((row) => selected.has(String(row.id)));
    }
    return searchResultRows;
  }, [searchResultRows, chartSelectedIds]);

  const colorMap = dataset?.cluster_color_map || {};
  const plotRows = searchActive
    ? (selectedCluster !== "" ? hierarchyFilteredRows.filter((row) => String(row.cluster) === String(selectedCluster)) : hierarchyFilteredRows)
    : textFilteredRows;
  const chartSelectedSet = useMemo(() => new Set(chartSelectedIds.map(String)), [chartSelectedIds]);
  const tableSelectedSet = useMemo(() => new Set(tableSelectedIds.map(String)), [tableSelectedIds]);
  const focusedPointSet = useMemo(() => {
    if (tableSelectedIds.length || chartSelectedIds.length) {
      return new Set([...tableSelectedIds, ...chartSelectedIds].map(String));
    }
    if (searchActive) {
      return searchResultSet;
    }
    return null;
  }, [chartSelectedIds, searchActive, searchResultSet, tableSelectedIds]);
  const explicitSelectedIds = useMemo(
    () => [...new Set([...chartSelectedIds, ...tableSelectedIds].map(String))],
    [chartSelectedIds, tableSelectedIds],
  );
  const activeSearchIds = useMemo(() => searchActive ? searchResultRows.map((row) => String(row.id)) : [], [searchActive, searchResultRows]);
  const canAnalyzeSelection = explicitSelectedIds.length > 0 || activeSearchIds.length > 0 || selectedCluster !== "";
  const rowById = useMemo(() => new Map(sourceRows.map((row) => [String(row.id), row])), [sourceRows]);
  const rowByNodeId = useMemo(() => {
    const rows = new Map();
    sourceRows.forEach((row) => {
      const nodeId = rowNodeId(row);
      if (nodeId) rows.set(nodeId, row);
    });
    return rows;
  }, [sourceRows]);
  const retrievalRankById = useMemo(() => {
    const ranks = new Map();
    (retrievalResult?.results || []).forEach((item) => ranks.set(String(item.id), Number(item.rank)));
    return ranks;
  }, [retrievalResult]);
  const retrievalScoreById = useMemo(() => {
    const scores = new Map();
    (retrievalResult?.results || []).forEach((item) => scores.set(String(item.id), Number(item.score)));
    return scores;
  }, [retrievalResult]);
  const hierarchyTrace = useMemo(() => {
    const selectedId = inspectedRow?.id || explicitSelectedIds[0] || retrievalResult?.results?.[0]?.id || "";
    const start = rowById.get(String(selectedId));
    if (!start) return [];
    const trace = [start];
    const visited = new Set([rowNodeId(start)]);
    let parentId = rowParentId(start);
    while (parentId && rowByNodeId.has(parentId) && !visited.has(parentId) && trace.length < 20) {
      const parent = rowByNodeId.get(parentId);
      trace.unshift(parent);
      visited.add(parentId);
      parentId = rowParentId(parent);
    }
    return trace;
  }, [explicitSelectedIds, inspectedRow, retrievalResult, rowById, rowByNodeId]);
  const childrenByParent = useMemo(() => {
    const children = new Map();
    sourceRows.forEach((row) => {
      const parentId = rowParentId(row);
      if (!parentId) return;
      if (!children.has(parentId)) children.set(parentId, []);
      children.get(parentId).push(row);
    });
    return children;
  }, [sourceRows]);
  const nearestById = useMemo(() => {
    const rows = sourceRows.filter((row) => Number.isFinite(Number(row.x)) && Number.isFinite(Number(row.y)));
    const result = new Map();
    const limit = Math.min(rows.length, 2500);
    for (let index = 0; index < limit; index += 1) {
      const row = rows[index];
      let nearest = null;
      let bestDistance = Number.POSITIVE_INFINITY;
      const z1 = Number(row.z || 0);
      for (let otherIndex = 0; otherIndex < limit; otherIndex += 1) {
        if (index === otherIndex) continue;
        const other = rows[otherIndex];
        const dx = Number(row.x) - Number(other.x);
        const dy = Number(row.y) - Number(other.y);
        const dz = z1 - Number(other.z || 0);
        const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (distance < bestDistance) {
          bestDistance = distance;
          nearest = other;
        }
      }
      if (nearest) result.set(String(row.id), { row: nearest, distance: bestDistance, similarity: 1 / (1 + bestDistance) });
    }
    return result;
  }, [sourceRows]);
  const qualityById = useMemo(() => {
    const qualities = new Map();
    sourceRows.forEach((row) => {
      const text = String(row.preview || "");
      const speakers = new Set([
        ...splitSpeakerValues(row["meta.speaker"] ?? row.metadata?.speaker ?? row.speaker),
        ...splitSpeakerValues(row["meta.speakers"] ?? row.metadata?.speakers ?? row.speakers),
      ]);
      const childCount = childrenByParent.get(rowNodeId(row))?.length || 0;
      const childIds = row["meta.child_ids"] ?? row.metadata?.child_ids;
      const declaredChildCount = Array.isArray(childIds) ? childIds.length : childCount;
      const start = numericMeta(row, ["start_time", "start"]);
      const end = numericMeta(row, ["end_time", "end"]);
      const duration = start !== null && end !== null ? Math.max(0, end - start) : null;
      const parent = rowByNodeId.get(rowParentId(row));
      const parentDistance = parent ? Math.sqrt(
        Math.pow(Number(row.x || 0) - Number(parent.x || 0), 2)
        + Math.pow(Number(row.y || 0) - Number(parent.y || 0), 2)
        + Math.pow(Number(row.z || 0) - Number(parent.z || 0), 2),
      ) : null;
      qualities.set(String(row.id), {
        textLength: text.length,
        tokenEstimate: Math.ceil(text.split(/\s+/).filter(Boolean).length * 1.33),
        speakerCount: speakers.size,
        speakers: [...speakers],
        duration,
        parentCount: rowParentId(row) ? 1 : 0,
        childCount: Math.max(childCount, declaredChildCount),
        parentSimilarity: parentDistance === null ? null : 1 / (1 + parentDistance),
        nearest: nearestById.get(String(row.id)) || null,
      });
    });
    return qualities;
  }, [childrenByParent, nearestById, rowByNodeId, sourceRows]);
  const outlierRows = useMemo(() => {
    const scored = sourceRows
      .map((row) => ({ row, nearest: nearestById.get(String(row.id)), parentId: rowParentId(row) }))
      .filter((item) => item.nearest)
      .sort((left, right) => right.nearest.distance - left.nearest.distance);
    return scored.slice(0, 25).map((item) => ({
      ...item,
      orphan: Boolean(item.parentId && !rowByNodeId.has(item.parentId)),
    }));
  }, [nearestById, rowByNodeId, sourceRows]);
  const orphanRows = useMemo(() => (
    sourceRows.filter((row) => {
      const parentId = rowParentId(row);
      return parentId && !rowByNodeId.has(parentId);
    }).slice(0, 25)
  ), [rowByNodeId, sourceRows]);
  const selectedQuality = inspectedRow ? qualityById.get(String(inspectedRow.id)) : null;
  const whyResult = useMemo(() => {
    if (!inspectedRow) return null;
    const queryTokens = keywordTokens(prefs.semanticSearch);
    const textTokens = new Set(keywordTokens(inspectedDocument?.document || inspectedRow.preview));
    const overlap = [...new Set(queryTokens.filter((token) => textTokens.has(token)))].slice(0, 12);
    const metadata = inspectedDocument?.metadata || inspectedRow.metadata || {};
    const metadataOverlaps = Object.entries(metadata)
      .filter(([key, value]) => value !== null && value !== undefined && String(value).trim())
      .filter(([key, value]) => queryTokens.some((token) => String(value).toLowerCase().includes(token) || key.toLowerCase().includes(token)))
      .slice(0, 8);
    return {
      overlap,
      metadataOverlaps,
      score: retrievalScoreById.get(String(inspectedRow.id)),
      rank: retrievalRankById.get(String(inspectedRow.id)),
      nearest: nearestById.get(String(inspectedRow.id)),
      topic: inspectedRow.topic_label || inspectedRow.topic || "",
      cluster: inspectedRow.cluster,
      level: hierarchyLabel(hierarchyLevel(inspectedRow)),
    };
  }, [inspectedDocument, inspectedRow, nearestById, prefs.semanticSearch, retrievalRankById, retrievalScoreById]);
  const pipelineSummary = useMemo(() => {
    const levels = new Set(sourceRows.map((row) => hierarchyLevel(row)));
    const speakers = new Set();
    sourceRows.forEach((row) => {
      splitSpeakerValues(row["meta.speaker"] ?? row.metadata?.speaker ?? row.speaker).forEach((speaker) => speakers.add(speaker));
      splitSpeakerValues(row["meta.speakers"] ?? row.metadata?.speakers ?? row.speakers).forEach((speaker) => speakers.add(speaker));
    });
    return {
      loaded: sourceRows.length,
      visible: tableFilteredRows.length,
      clusters: (dataset?.topics || []).length,
      levels: levels.size,
      speakers: speakers.size,
      ranked: retrievalResult?.results?.length || highlightedIds.length || 0,
      orphans: sourceRows.filter((row) => rowParentId(row) && !rowByNodeId.has(rowParentId(row))).length,
    };
  }, [dataset, highlightedIds.length, retrievalResult, rowByNodeId, sourceRows, tableFilteredRows.length]);

  const plotData = useMemo(() => {
    if (!plotRows.length) return [];
    const is3d = prefs.dimensions === 3;
    const traceType = is3d ? "scatter3d" : "scatter";
    const common = {
      name: "Chunks",
      showlegend: false,
      mode: "markers",
      type: traceType,
      x: plotRows.map((row) => row.x),
      y: plotRows.map((row) => row.y),
      customdata: plotRows.map((row) => [row.id, row.preview, row.cluster]),
      text: plotRows.map((row) => short(row.preview, 240)),
      hoverinfo: prefs.hoverEnabled ? "text" : "none",
      hovertemplate: prefs.hoverEnabled ? "%{text}<extra></extra>" : null,
      marker: {
        size: 7,
        color: plotRows.map((row) => (prefs.colorMode === "cluster" ? clusterColor(row.cluster, colorMap) : "#8ea0ff")),
        line: {
          color: "rgba(255,255,255,0.45)",
          width: 0.6,
        },
        opacity: focusedPointSet ? plotRows.map((row) => (focusedPointSet.has(String(row.id)) ? 0.96 : 0.06)) : 0.9,
      },
      selectedpoints: null,
      selected: { marker: { opacity: 1 } },
      unselected: { marker: { opacity: 0.9 } },
    };
    if (is3d) {
      common.z = plotRows.map((row) => row.z || 0);
    }
    const overlayRows = plotRows.filter((row) => {
      const id = String(row.id);
      return highlightedSet.has(id) || chartSelectedSet.has(id) || tableSelectedSet.has(id) || retrievalRankById.has(id);
    });
    if (!overlayRows.length) return [common];
    const overlay = {
      name: "Selected",
      showlegend: false,
      mode: "markers",
      type: traceType,
      x: overlayRows.map((row) => row.x),
      y: overlayRows.map((row) => row.y),
      customdata: overlayRows.map((row) => [row.id, row.preview, row.cluster]),
      text: overlayRows.map((row) => {
        const rank = retrievalRankById.get(String(row.id));
        return rank ? `Rank ${rank} · score ${retrievalScoreById.get(String(row.id))?.toFixed?.(3) || ""}` : short(row.preview, 240);
      }),
      hoverinfo: prefs.hoverEnabled ? "text" : "none",
      hovertemplate: prefs.hoverEnabled ? "%{text}<extra></extra>" : null,
      marker: {
        size: overlayRows.map((row) => {
          const rank = retrievalRankById.get(String(row.id));
          return rank ? Math.max(11, 19 - Math.min(rank, 12) * 0.6) : 13;
        }),
        color: overlayRows.map((row) => {
          const id = String(row.id);
          if (retrievalRankById.has(id)) return retrievalRankColor(retrievalRankById.get(id));
          if (highlightedSet.has(id)) return "#ffd166";
          if (tableSelectedSet.has(id)) return "#7dd3fc";
          return "#ffffff";
        }),
        line: {
          color: overlayRows.map((row) => retrievalRankById.has(String(row.id)) ? "#ffffff" : "#1b1f2a"),
          width: overlayRows.map((row) => retrievalRankById.has(String(row.id)) ? 3 : 2),
        },
        opacity: 1,
      },
      selectedpoints: null,
      selected: { marker: { opacity: 1 } },
      unselected: { marker: { opacity: 1 } },
    };
    if (is3d) {
      overlay.z = overlayRows.map((row) => row.z || 0);
    }
    return [common, overlay];
  }, [chartSelectedSet, colorMap, focusedPointSet, highlightedSet, plotRows, prefs.colorMode, prefs.dimensions, prefs.hoverEnabled, retrievalRankById, retrievalScoreById, tableSelectedSet]);

  const handleChartWakeClick = useCallback((event) => {
    event?.preventDefault?.();
    setChartWakeButtonVisible(false);
    setChartWakePulse((current) => current + 1);
    chartWakeButtonRef.current?.focus?.({ preventScroll: true });
    chartWakeButtonRef.current?.blur?.();
    window.dispatchEvent(new Event("resize"));
  }, []);

  const updateLlmAuditSetting = useCallback((key, value) => {
    setLlmAuditSettings((current) => ({ ...current, [key]: value }));
  }, []);

  const llmProviderPayload = () => ({
    provider: llmAuditSettings.provider,
    base_url: llmAuditSettings.baseUrl,
    model: llmAuditSettings.model,
    api_key: llmAuditSettings.apiKey,
  });

  const refreshLlmModels = async () => {
    if (llmAuditSettings.provider === "Disabled" || !llmAuditSettings.baseUrl.trim()) return;
    setLlmModelsLoading(true);
    setError("");
    try {
      const result = await callApi("/api/llm/models", {
        method: "POST",
        body: JSON.stringify({ provider: llmProviderPayload() }),
      });
      const models = result.models || [];
      setLlmModelNames(models);
      setLlmModelDetails(result.model_details || {});
      if (!llmAuditSettings.model && models.length) {
        updateLlmAuditSetting("model", models[0]);
      }
    } catch (err) {
      setLlmModelNames([]);
      setLlmModelDetails({});
      setError(`LLM model lookup failed: ${readableError(err)}`);
    } finally {
      setLlmModelsLoading(false);
    }
  };

  useEffect(() => {
    if (chartWakeTimerRef.current) window.clearTimeout(chartWakeTimerRef.current);
    setChartWakeButtonVisible(false);

    if (!plotRows.length || loading) return undefined;

    setChartWakeButtonVisible(true);
    chartWakeTimerRef.current = window.setTimeout(() => {
      chartWakeButtonRef.current?.click();
    }, 1200);

    return () => {
      if (chartWakeTimerRef.current) window.clearTimeout(chartWakeTimerRef.current);
    };
  }, [dataset, handleChartWakeClick, loading, plotRows.length, prefs.dimensions, selectedCollection]);

  const plotLayout = useMemo(() => {
    const axisPrefix = prefs.reductionMethod === "PCA" ? "PCA" : "UMAP";
    const dimensionView = plotViewsByDimensionRef.current[String(prefs.dimensions)] || plotRelayoutRef.current || plotRelayout;
    const baseXaxis = {
      title: `${axisPrefix} 1`,
      gridcolor: "#232a39",
      zerolinecolor: "#232a39",
    };
    const baseYaxis = {
      title: `${axisPrefix} 2`,
      gridcolor: "#232a39",
      zerolinecolor: "#232a39",
    };
    const baseScene = {
      bgcolor: "#10131b",
      xaxis: { title: `${axisPrefix} 1`, gridcolor: "#293244", color: "#d8deee" },
      yaxis: { title: `${axisPrefix} 2`, gridcolor: "#293244", color: "#d8deee" },
      zaxis: { title: `${axisPrefix} 3`, gridcolor: "#293244", color: "#d8deee" },
    };
    return {
      autosize: true,
      paper_bgcolor: "#10131b",
      plot_bgcolor: "#10131b",
      margin: { l: 44, r: 20, t: 18, b: 42 },
      dragmode: dragMode,
      font: { color: "#d8deee" },
      hoverlabel: {
        bgcolor: "#1d2330",
        bordercolor: "#4a5878",
        font: { color: "#f2f5ff", size: 12 },
        align: "left",
      },
      showlegend: false,
      uirevision: `${selectedCollection}-${prefs.dimensions}`,
      xaxis: { ...baseXaxis, ...(dimensionView.xaxis || {}) },
      yaxis: { ...baseYaxis, ...(dimensionView.yaxis || {}) },
      scene: { ...baseScene, ...(dimensionView.scene || {}) },
      selectionrevision: selectionRevision,
    };
  }, [dragMode, plotRelayout, prefs.dimensions, prefs.reductionMethod, selectedCollection, selectionRevision]);

  const clusterRows = useMemo(() => {
    const topics = dataset?.topics || [];
    return topics.map((topic) => ({
      ...topic,
      color: clusterColor(topic.cluster, colorMap),
    }));
  }, [colorMap, dataset]);

  const visibleTableRows = useMemo(() => tableFilteredRows.slice(0, 2000), [tableFilteredRows]);

  const clearSelections = useCallback(() => {
    setChartSelectedIds([]);
    setTableSelectedIds([]);
    setHighlightedIds([]);
    setAnalysisResult(null);
    setRetrievalResult(null);
    setCompareResult(null);
    setHoverPreview("");
    setSelectedCluster("");
    setPrefs((current) => ({ ...current, textSearch: "", semanticSearch: "", hierarchyLevels: null }));
    setDragMode("pan");
    setSelectionRevision((current) => current + 1);
  }, []);

  const handlePlotSelected = (event) => {
    const ids = event?.points?.map((point) => point.customdata?.[0]).filter(Boolean) || [];
    setChartSelectedIds([...new Set(ids.map(String))]);
  };

  const handlePlotClick = (event) => {
    lastPlotClickRef.current = Date.now();
    const id = event?.points?.[0]?.customdata?.[0];
    if (!id) return;
    const row = sourceRows.find((item) => String(item.id) === String(id));
    setInspectedRow(row || null);
    setChartSelectedIds([String(id)]);
  };

  const handlePlotHover = (event) => {
    if (!prefs.hoverEnabled) return;
    const point = event?.points?.[0];
    const id = point?.customdata?.[0];
    const preview = point?.customdata?.[1] || point?.text || "";
    hoveredPointRef.current = id ? { id: String(id), preview: String(preview) } : null;
    if (hoverResetTimerRef.current) window.clearTimeout(hoverResetTimerRef.current);
    setHoverPreview(String(preview));
    hoverResetTimerRef.current = window.setTimeout(() => {
      setHoverPreview("");
    }, 5000);
  };

  const handleChartMouseLeave = () => {
    if (hoverResetTimerRef.current) window.clearTimeout(hoverResetTimerRef.current);
    hoveredPointRef.current = null;
    setHoverPreview("");
  };

  const selectHoveredPoint = () => {
    window.setTimeout(() => {
      if (Date.now() - lastPlotClickRef.current < 120) return;
      const hovered = hoveredPointRef.current;
      if (!hovered?.id) return;
      const row = sourceRows.find((item) => String(item.id) === hovered.id);
      setInspectedRow(row || null);
      setChartSelectedIds([hovered.id]);
    }, 0);
  };

  const handlePlotReady = useCallback((_figure, graphDiv) => {
    window.requestAnimationFrame(() => {
      window.Plotly?.Plots?.resize(graphDiv);
    });
  }, []);

  const handleSemanticSearch = async () => {
    if (!prefs.semanticSearch.trim() || !selectedCollection) return;
    setError("");
    setSemanticLoading(true);
    setRetrievalResult(null);
    setCompareResult(null);
    try {
      const restrictToCandidates = Boolean(prefs.textSearch.trim() || selectedCluster !== "");
      const candidateRows = restrictToCandidates ? textFilteredRows : sourceRows;
      if (!candidateRows.length) {
        setHighlightedIds([]);
        setAnalysisResult(null);
        return;
      }
      const result = await runRetrievalExperiment("Semantic Search", candidateRows, true);
      const resultIds = (result.ids || []).map(String);
      setHighlightedIds(resultIds);
      setChartSelectedIds([]);
      setTableSelectedIds([]);
      if (resultIds.length) {
        handleAnalyzeSelection(resultIds);
      } else {
        setAnalysisResult(null);
      }
    } catch (err) {
      setError(`Semantic search failed: ${err.message}`);
      setHighlightedIds([]);
      setAnalysisResult(null);
    } finally {
      setSemanticLoading(false);
    }
  };

  const runRetrievalExperiment = async (mode = "Current filtered set", candidateRows = textFilteredRows, updateView = true) => {
    if (!prefs.semanticSearch.trim() || !selectedCollection || !pathValid) return null;
    const candidateIds = candidateRows.map((row) => String(row.id));
    if (!candidateIds.length) {
      throw new Error(`${mode} has no candidate chunks to search.`);
    }
    const result = await callApi("/api/retrieval-experiment", {
      method: "POST",
      body: JSON.stringify({
        chroma_path: chromaPath,
        collection_name: selectedCollection,
        query: prefs.semanticSearch,
        top_k: prefs.semanticTopK,
        candidate_ids: candidateIds,
        mode,
      }),
    });
    if (updateView) {
      const resultIds = (result.ids || []).map(String);
      setRetrievalResult(result);
      setHighlightedIds(resultIds);
      setChartSelectedIds([]);
      setTableSelectedIds([]);
      setInfoTab("Retrieval");
    }
    return result;
  };

  const handleRetrievalExperiment = async () => {
    setRetrievalLoading(true);
    setError("");
    try {
      await runRetrievalExperiment("Current filtered set", textFilteredRows, true);
    } catch (err) {
      setError(`Retrieval experiment failed: ${err.message}`);
      setRetrievalResult(null);
    } finally {
      setRetrievalLoading(false);
    }
  };

  const compareRetrievalModes = async () => {
    if (!prefs.semanticSearch.trim() || !selectedCollection || !pathValid) return;
    const modes = [
      { name: "Current Filters", rows: textFilteredRows },
      { name: "All Loaded", rows: sourceRows },
      { name: "Leaf Chunks", rows: sourceRows.filter((row) => hierarchyLevel(row) === "leaf") },
      { name: "Summaries", rows: sourceRows.filter((row) => hierarchyLevel(row).startsWith("summary_")) },
      { name: "Claims / Positions", rows: sourceRows.filter((row) => ["position", "episode"].includes(hierarchyLevel(row))) },
    ].filter((mode) => mode.rows.length);
    setCompareLoading(true);
    setError("");
    try {
      const results = await Promise.all(
        modes.map(async (mode) => ({
          name: mode.name,
          candidateCount: mode.rows.length,
          result: await runRetrievalExperiment(mode.name, mode.rows, false),
        })),
      );
      setCompareResult(results);
      setInfoTab("Compare");
    } catch (err) {
      setError(`Compare retrieval modes failed: ${err.message}`);
      setCompareResult(null);
    } finally {
      setCompareLoading(false);
    }
  };

  const saveRetrievalRun = () => {
    if (!retrievalResult) return;
    const run = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      name: `${selectedCollection || "Collection"} · ${short(retrievalResult.query || prefs.semanticSearch, 42)}`,
      timestamp: new Date().toISOString(),
      collection: selectedCollection,
      chromaPath,
      query: retrievalResult.query || prefs.semanticSearch,
      topK: prefs.semanticTopK,
      filters: {
        textSearch: prefs.textSearch,
        hierarchyLevels: Array.isArray(prefs.hierarchyLevels) ? prefs.hierarchyLevels : null,
        selectedCluster,
      },
      ids: retrievalResult.ids || [],
      scores: retrievalResult.results || [],
      notes: retrievalNotes,
    };
    setSavedRuns((current) => [run, ...current.filter((item) => item.id !== run.id)].slice(0, 50));
  };

  const loadRetrievalRun = (run) => {
    setPrefs((current) => ({
      ...current,
      semanticSearch: run.query || "",
      semanticTopK: run.topK || current.semanticTopK,
      textSearch: run.filters?.textSearch || "",
      hierarchyLevels: run.filters?.hierarchyLevels || null,
    }));
    setSelectedCluster(run.filters?.selectedCluster || "");
    setRetrievalResult({
      query: run.query,
      mode: "Saved run",
      ids: run.ids || [],
      results: run.scores || [],
      histogram: [],
      candidate_count: run.scores?.length || run.ids?.length || 0,
      embedding_dim: dataset?.metrics?.embedding_dim,
    });
    setHighlightedIds((run.ids || []).map(String));
    setRetrievalNotes(run.notes || "");
    setChartSelectedIds([]);
    setTableSelectedIds([]);
    setInfoTab("Retrieval");
  };

  const exportRetrievalReport = () => {
    if (!retrievalResult) return;
    const lines = [
      `# Retrieval Report: ${selectedCollection || "Collection"}`,
      "",
      `- Query: ${retrievalResult.query || prefs.semanticSearch}`,
      `- Mode: ${retrievalResult.mode || "Current filtered set"}`,
      `- Top K: ${prefs.semanticTopK}`,
      `- Candidates scored: ${retrievalResult.candidate_count || 0}`,
      `- Generated: ${new Date().toISOString()}`,
      ...(retrievalNotes.trim() ? ["", "## Notes", "", retrievalNotes.trim()] : []),
      "",
      "## Ranked Results",
      "",
      "| Rank | Score | Level | Cluster | Source | Preview |",
      "| ---: | ---: | --- | --- | --- | --- |",
      ...(retrievalResult.results || []).map((item) => {
        const row = rowById.get(String(item.id));
        return `| ${item.rank} | ${item.score} | ${hierarchyLabel(hierarchyLevel(row || item))} | ${row?.cluster ?? ""} | ${String(row?.source || item.source || "").replace(/\|/g, "\\|")} | ${short(row?.preview || item.preview, 140).replace(/\|/g, "\\|")} |`;
      }),
      "",
      "## Score Distribution",
      "",
      ...(retrievalResult.histogram || []).map((bucket) => `- ${bucket.start} to ${bucket.end}: ${bucket.count}`),
    ];
    downloadText(`${selectedCollection || "retrieval"}-report.md`, lines.join("\n"), "text/markdown;charset=utf-8");
  };

  const retrievalRequest = async (query, mode, candidateRows, topK = prefs.semanticTopK) => {
    if (!query.trim() || !selectedCollection || !pathValid) return null;
    const candidateIds = candidateRows.map((row) => String(row.id));
    if (!candidateIds.length) throw new Error(`${mode} has no candidate chunks to search.`);
    return callApi("/api/retrieval-experiment", {
      method: "POST",
      body: JSON.stringify({
        chroma_path: chromaPath,
        collection_name: selectedCollection,
        query,
        top_k: topK,
        candidate_ids: candidateIds,
        mode,
      }),
    });
  };

  const generateAuditQueries = async () => {
    if (llmAuditSettings.provider === "Disabled") return;
    setQueryGenerationLoading(true);
    setError("");
    try {
      const sampleRows = sourceRows.slice(0, 80).filter((_, index) => index % 4 === 0).slice(0, 20);
      const result = await callApi("/api/llm/generate-audit-queries", {
        method: "POST",
        body: JSON.stringify({
          provider: llmProviderPayload(),
          collection_name: selectedCollection,
          sample_chunks: sampleRows.map((row) => ({
            id: row.id,
            level: hierarchyLevel(row),
            title: row.title,
            source: row.source,
            preview: row.preview,
          })),
          existing_queries: auditQueries.split(/\r?\n/).map((line) => line.trim()).filter(Boolean),
          query_count: auditPreset === "Quick Scan" ? 4 : 10,
        }),
      });
      if (result.queries?.length) {
        setAuditQueries(result.queries.join("\n"));
      } else {
        setError("LLM query generation returned no queries.");
      }
    } catch (err) {
      setError(`LLM query generation failed: ${err.message}`);
    } finally {
      setQueryGenerationLoading(false);
    }
  };

  const exportAuditQueries = () => {
    const payload = {
      collection: selectedCollection,
      timestamp: new Date().toISOString(),
      queries: auditQueries.split(/\r?\n/).map((line) => line.trim()).filter(Boolean),
    };
    downloadText(`${selectedCollection || "audit"}-queries.json`, JSON.stringify(payload, null, 2), "application/json;charset=utf-8");
  };

  const importAuditQueries = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const queries = Array.isArray(parsed) ? parsed : parsed.queries;
      if (!Array.isArray(queries)) throw new Error("JSON must be an array or an object with a queries array.");
      setAuditQueries(queries.map(String).filter(Boolean).join("\n"));
    } catch (err) {
      setError(`Query import failed: ${err.message}`);
    } finally {
      event.target.value = "";
    }
  };

  const collectAuditContexts = async (report) => {
    const ids = [];
    (report.retrieval?.tests || []).forEach((test) => {
      (test.modes || []).forEach((mode) => {
        (mode.results || []).slice(0, 1).forEach((item) => ids.push(String(item.id)));
      });
    });
    const uniqueIds = [...new Set(ids)].slice(0, 8);
    const contexts = [];
    for (const id of uniqueIds) {
      const row = rowById.get(id);
      if (!row) continue;
      let text = row.preview || "";
      let metadata = row.metadata || {};
      if (!llmAuditSettings.limitContext) {
        try {
          const document = await callApi("/api/document", {
            method: "POST",
            body: JSON.stringify({ chroma_path: chromaPath, collection_name: selectedCollection, id }),
          });
          text = document.document || text;
          metadata = document.metadata || metadata;
        } catch {
          // Keep the preview fallback if a full document lookup fails.
        }
      }
      contexts.push({
        id,
        level: hierarchyLabel(hierarchyLevel(row)),
        source: row.source,
        title: row.title,
        cluster: row.cluster,
        text: short(text, llmAuditSettings.limitContext ? 220 : 650),
        metadata: llmAuditSettings.limitContext ? { source: row.source, title: row.title, level: hierarchyLevel(row) } : metadata,
      });
    }
    return contexts;
  };

  const interpretAuditWithLlm = async (report) => {
    if (llmAuditSettings.provider === "Disabled") return null;
    const contexts = await collectAuditContexts(report);
    const compactReport = {
      collection: report.collection,
      preset: report.preset,
      scope: report.scope,
      scores: report.scores,
      database: report.database,
      findings: report.findings,
      metadata: report.metadata,
      hierarchy: {
        orphanCount: report.hierarchy?.orphanCount || 0,
        orphanExamples: (report.hierarchy?.orphanExamples || []).slice(0, 5),
      },
      embeddings: {
        outlierCount: report.embeddings?.outlierCount || 0,
        duplicateGroups: report.embeddings?.duplicates?.length || 0,
        outlierExamples: (report.embeddings?.outlierExamples || []).slice(0, 5),
      },
      retrieval: {
        queryCount: report.retrieval?.queryCount || 0,
        tests: (report.retrieval?.tests || []).slice(0, 5).map((test) => ({
          query: test.query,
          modes: (test.modes || []).map((mode) => ({
            name: mode.name,
            candidateCount: mode.candidateCount,
            topScore: mode.topScore,
            scoreSpread: mode.scoreSpread,
            results: (mode.results || []).slice(0, 3).map((item) => ({
              id: item.id,
              rank: item.rank,
              score: item.score,
              level: item.level,
              preview: short(item.preview, 180),
            })),
          })),
        })),
      },
    };
    return callApi("/api/llm/interpret-audit", {
      method: "POST",
      body: JSON.stringify({
        provider: llmProviderPayload(),
        audit_report: compactReport,
        contexts,
        limit_context: llmAuditSettings.limitContext,
      }),
    });
  };

  const buildDeterministicAudit = async () => {
    const rows = auditScope === "Current Filters" ? textFilteredRows : sourceRows;
    const includeRetrieval = auditPreset !== "Metadata / Hierarchy Only";
    const queries = includeRetrieval
      ? auditQueries.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).slice(0, auditPreset === "Quick Scan" ? 2 : 8)
      : [];
    const requiredFields = ["source", "title", "level", "speaker"];
    const fieldStats = requiredFields.map((field) => {
      const present = rows.filter((row) => {
        const value = row[field] ?? row[`meta.${field}`] ?? row.metadata?.[field];
        return value !== undefined && value !== null && String(value).trim() !== "";
      }).length;
      return { field, present, missing: rows.length - present, completeness: percent(present, rows.length) };
    });
    const duplicateGroups = new Map();
    rows.forEach((row) => {
      const key = String(row.preview || "").toLowerCase().replace(/\s+/g, " ").trim().slice(0, 220);
      if (!key) return;
      if (!duplicateGroups.has(key)) duplicateGroups.set(key, []);
      duplicateGroups.get(key).push(String(row.id));
    });
    const duplicates = [...duplicateGroups.entries()]
      .filter(([, ids]) => ids.length > 1)
      .slice(0, 20)
      .map(([preview, ids]) => ({ preview, ids, count: ids.length }));
    const levels = hierarchyOptions.map((option) => ({
      level: option.level,
      label: option.label,
      count: rows.filter((row) => hierarchyLevel(row) === option.level).length,
    })).filter((item) => item.count);
    const retrievalModes = [
      { name: "All Loaded", rows },
      { name: "Leaf Chunks", rows: rows.filter((row) => hierarchyLevel(row) === "leaf") },
      { name: "Summaries", rows: rows.filter((row) => hierarchyLevel(row).startsWith("summary_")) },
      { name: "Claims / Positions", rows: rows.filter((row) => ["position", "episode"].includes(hierarchyLevel(row))) },
    ].filter((mode) => mode.rows.length);
    const retrievalTests = [];
    for (const query of queries) {
      const modes = [];
      for (const mode of retrievalModes) {
        const result = await retrievalRequest(query, mode.name, mode.rows, Math.min(10, prefs.semanticTopK || 10));
        const scores = result?.results?.map((item) => Number(item.score)).filter(Number.isFinite) || [];
        modes.push({
          name: mode.name,
          candidateCount: mode.rows.length,
          topScore: scores[0] || null,
          scoreSpread: scores.length > 1 ? Math.round((scores[0] - scores[scores.length - 1]) * 1000) / 1000 : null,
          results: (result?.results || []).slice(0, 5),
          histogram: result?.histogram || [],
        });
      }
      retrievalTests.push({ query, modes });
    }
    const metadataScore = scoreFromPercent(fieldStats.reduce((sum, item) => sum + item.completeness, 0) / Math.max(1, fieldStats.length));
    const hierarchyScore = scoreFromPercent(100 - percent(orphanRows.length, rows.length));
    const duplicatePenalty = Math.min(30, duplicates.reduce((sum, item) => sum + item.count - 1, 0));
    const embeddingScore = scoreFromPercent(100 - Math.min(40, outlierRows.length ? percent(outlierRows.length, rows.length) : 0) - duplicatePenalty);
    const retrievalScore = includeRetrieval ? scoreFromPercent(
      retrievalTests.length
        ? retrievalTests.reduce((sum, test) => sum + Math.max(...test.modes.map((mode) => Number(mode.topScore || 0))) * 100, 0) / retrievalTests.length
        : 0,
    ) : 100;
    const overallScore = Math.round((metadataScore + hierarchyScore + embeddingScore + retrievalScore) / 4);
    return {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      timestamp: new Date().toISOString(),
      preset: auditPreset,
      scope: auditScope,
      collection: selectedCollection,
      chromaPath,
      scores: { overall: overallScore, metadata: metadataScore, hierarchy: hierarchyScore, embeddings: embeddingScore, retrieval: retrievalScore },
      database: {
        loadedRows: rows.length,
        embeddingDimension: dataset?.metrics?.embedding_dim || null,
        clusterer: dataset?.metrics?.clusterer || "",
        clusters: pipelineSummary.clusters,
        speakers: pipelineSummary.speakers,
        levels,
      },
      metadata: { requiredFields: fieldStats },
      hierarchy: { orphanCount: orphanRows.length, orphanExamples: orphanRows.slice(0, 12).map((row) => ({ id: row.id, parentId: rowParentId(row), preview: row.preview })) },
      embeddings: {
        outlierCount: outlierRows.length,
        outlierExamples: outlierRows.slice(0, 12).map((item) => ({ id: item.row.id, nearestFit: item.nearest.similarity, level: hierarchyLevel(item.row), preview: item.row.preview })),
        duplicates,
      },
      retrieval: { queryCount: retrievalTests.length, tests: retrievalTests },
      findings: [
        ...(fieldStats.filter((item) => item.missing).map((item) => `${item.field} missing on ${item.missing.toLocaleString()} chunks.`)),
        ...(orphanRows.length ? [`${orphanRows.length.toLocaleString()} hierarchy nodes reference missing parents in the loaded scope.`] : []),
        ...(duplicates.length ? [`${duplicates.length.toLocaleString()} duplicate or near-duplicate preview groups were found.`] : []),
        ...(outlierRows.length ? [`${outlierRows.length.toLocaleString()} projected outlier candidates are worth inspecting.`] : []),
      ],
    };
  };

  const runAudit = async () => {
    if (!sourceRows.length || !selectedCollection || !pathValid) return;
    setAuditLoading(true);
    setError("");
    try {
      const report = await buildDeterministicAudit();
      if (llmAuditSettings.provider !== "Disabled") {
        report.llm = await interpretAuditWithLlm(report);
        const warnings = report.llm?.diagnostics?.warnings || [];
        const detectedContext = report.llm?.diagnostics?.context_window;
        if (detectedContext && llmAuditSettings.model) {
          setLlmModelDetails((current) => ({
            ...current,
            [llmAuditSettings.model]: {
              ...(current[llmAuditSettings.model] || {}),
              context_length: detectedContext,
            },
          }));
        }
        if (warnings.length) {
          addToast({
            id: "llm-audit-diagnostics",
            type: "warning",
            title: "LLM Audit Warning",
            message: warnings.join(" "),
            autoClose: false,
          });
        }
      }
      setAuditReport(report);
      setSavedAudits((current) => [report, ...current.filter((item) => item.id !== report.id)].slice(0, 20));
      setWorkspaceMode("Audit Report");
      setActiveSection("Audit");
    } catch (err) {
      setError(`RAG quality audit failed: ${readableError(err)}`);
    } finally {
      setAuditLoading(false);
    }
  };

  const exportAuditReport = (format = "json") => {
    if (!auditReport) return;
    if (format === "json") {
      downloadText(`${selectedCollection || "chromadb"}-audit.json`, JSON.stringify(auditReport, null, 2), "application/json;charset=utf-8");
      return;
    }
    const lines = [
      `# RAG Quality Audit: ${auditReport.collection}`,
      "",
      `- Generated: ${auditReport.timestamp}`,
      `- Preset: ${auditReport.preset}`,
      `- Scope: ${auditReport.scope}`,
      `- Overall score: ${auditReport.scores.overall}`,
      "",
      "## Scores",
      "",
      ...Object.entries(auditReport.scores).map(([key, value]) => `- ${key}: ${value}`),
      "",
      "## Findings",
      "",
      ...(auditReport.findings.length ? auditReport.findings.map((finding) => `- ${finding}`) : ["- No major deterministic findings."]),
      ...(auditReport.llm?.enabled ? [
        "",
        "## LLM Interpretation",
        "",
        auditReport.llm.summary || "",
        "",
        "### Recommended Actions",
        "",
        ...(auditReport.llm.recommended_actions || []).map((item) => `- ${item}`),
      ] : []),
      "",
      "## Retrieval Tests",
      "",
      ...auditReport.retrieval.tests.flatMap((test) => [
        `### ${test.query}`,
        "",
        ...test.modes.map((mode) => `- ${mode.name}: top score ${mode.topScore ?? "n/a"}, spread ${mode.scoreSpread ?? "n/a"}, candidates ${mode.candidateCount}`),
        "",
      ]),
    ];
    downloadText(`${selectedCollection || "chromadb"}-audit.md`, lines.join("\n"), "text/markdown;charset=utf-8");
  };

  const copyModalText = async () => {
    if (!messageModal?.text) return;
    try {
      await navigator.clipboard.writeText(messageModal.text);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = messageModal.text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    }
  };

  const handleAnalyzeSelection = async (overrideIds = null) => {
    const idsToAnalyze = Array.isArray(overrideIds)
      ? overrideIds
      : explicitSelectedIds.length
        ? explicitSelectedIds
        : activeSearchIds.length
          ? activeSearchIds
        : selectedCluster !== ""
          ? sourceRows.filter((row) => String(row.cluster) === String(selectedCluster)).map((row) => String(row.id))
          : [];
    if (!idsToAnalyze.length || !selectedCollection || !pathValid) return;
    if (idsToAnalyze.length > MAX_ANALYSIS_IDS) {
      setError(`Selection analysis skipped: ${idsToAnalyze.length.toLocaleString()} points exceeds the ${MAX_ANALYSIS_IDS.toLocaleString()} point analysis limit.`);
      setAnalysisResult(null);
      return;
    }
    setAnalysisLoading(true);
    setError("");
    try {
      const result = await callApi("/api/analyze-selection", {
        method: "POST",
        body: JSON.stringify({
          chroma_path: chromaPath,
          collection_name: selectedCollection,
          max_load_size: prefs.maxLoad,
          chart_view: prefs.dimensions === 3 ? "3D" : "2D",
          reduction: {
            method: prefs.reductionMethod,
            n_neighbors: 15,
            min_dist: 0.1,
            use_sampling: prefs.sampling,
            sample_size: prefs.maxLoad,
          },
          clustering: {
            method: prefs.clusteringMethod,
            kmeans_clusters: prefs.clusterCount,
            hdbscan_min_cluster_size: prefs.minClusterSize,
          },
          selected_ids: idsToAnalyze,
        }),
      });
      setAnalysisResult(result);
    } catch (err) {
      setError(`Selection analysis failed: ${err.message}`);
      setAnalysisResult(null);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const startTableResize = (event) => {
    event.preventDefault();
    const startY = event.clientY;
    const startHeight = tableHeight;
    const onMove = (moveEvent) => {
      const next = Math.max(160, Math.min(720, startHeight - (moveEvent.clientY - startY)));
      setTableHeight(next);
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  const startRightResize = (event) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = rightWidth;
    const onMove = (moveEvent) => {
      const next = Math.max(280, Math.min(620, startWidth - (moveEvent.clientX - startX)));
      setRightWidth(next);
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  const loadViews = useCallback(async () => {
    try {
      const result = await callApi("/api/views");
      setSavedViews(result.views || []);
    } catch {
      setSavedViews([]);
    }
  }, [callApi]);

  useEffect(() => {
    loadViews();
  }, [loadViews]);

  const saveView = async () => {
    if (!viewName.trim()) return;
    await callApi("/api/views", {
      method: "POST",
      body: JSON.stringify({
        name: viewName,
        description: viewDescription,
        state: {
          chroma_path: chromaPath,
          collection_name: selectedCollection,
          sidebar: prefs,
          selected_points: chartSelectedIds,
          table_selected_points: tableSelectedIds,
          highlighted_neighbors: highlightedIds,
          plot_relayout: plotRelayoutRef.current,
          plot_views: plotViewsByDimensionRef.current,
          table_height: tableHeight,
          right_width: rightWidth,
        },
      }),
    });
    setViewName("");
    setViewDescription("");
    loadViews();
  };

  const applySavedView = (view) => {
    const state = view.state || {};
    if (state.chroma_path) setChromaPath(state.chroma_path);
    if (state.collection_name) setSelectedCollection(state.collection_name);
    const restoredPrefs = {
      ...(state.sidebar_settings || {}),
      ...(state.sidebar || {}),
    };
    if (state.reduction?.method) restoredPrefs.reductionMethod = state.reduction.method;
    if (state.clustering?.method) restoredPrefs.clusteringMethod = state.clustering.method;
    if (state.clustering?.kmeans_clusters) restoredPrefs.clusterCount = state.clustering.kmeans_clusters;
    if (state.clustering?.hdbscan_min_cluster_size) restoredPrefs.minClusterSize = state.clustering.hdbscan_min_cluster_size;
    if (state.max_load_size) restoredPrefs.maxLoad = state.max_load_size;
    if (state.chart_view) restoredPrefs.dimensions = state.chart_view === "3D" ? 3 : 2;
    if (state.color_mode) restoredPrefs.colorMode = state.color_mode;
    if (state.text_search_query !== undefined) restoredPrefs.textSearch = state.text_search_query;
    if (state.semantic_search_query !== undefined) restoredPrefs.semanticSearch = state.semantic_search_query;
    if (state.semantic_top_k) restoredPrefs.semanticTopK = state.semantic_top_k;
    if (state.popup_delay_seconds !== undefined) restoredPrefs.popupDelay = state.popup_delay_seconds;
    if (state.popups_enabled !== undefined) restoredPrefs.hoverEnabled = state.popups_enabled;
    setPrefs((current) => ({ ...current, ...restoredPrefs }));
    if (state.selected_points || state.selected_ids) setChartSelectedIds(state.selected_points || state.selected_ids);
    if (state.table_selected_points) setTableSelectedIds(state.table_selected_points);
    if (state.highlighted_neighbors || state.highlighted_ids) setHighlightedIds(state.highlighted_neighbors || state.highlighted_ids);
    if (state.plot_relayout || state.plot_view) {
      const restoredPlotView = normalizeStoredPlotView(state.plot_relayout || state.plot_view, restoredPrefs.dimensions || prefs.dimensions);
      plotRelayoutRef.current = restoredPlotView;
      setPlotRelayout(restoredPlotView);
    }
    if (state.plot_views) {
      const normalizedViews = Object.fromEntries(
        Object.entries(state.plot_views).map(([key, value]) => [key, normalizeStoredPlotView(value, Number(key))]),
      );
      plotViewsByDimensionRef.current = normalizedViews;
      setPlotViewsByDimension(normalizedViews);
    }
    if (state.table_height) setTableHeight(state.table_height);
    if (state.right_width) setRightWidth(state.right_width);
  };

  const deleteView = async (filename) => {
    await callApi(`/api/views/${encodeURIComponent(filename)}`, { method: "DELETE" });
    loadViews();
  };

  const renameView = async (view) => {
    const nextName = window.prompt("Rename saved view", view.name || view.filename);
    if (!nextName || nextName.trim() === (view.name || "").trim()) return;
    await callApi(`/api/views/${encodeURIComponent(view.filename)}/rename`, {
      method: "PUT",
      body: JSON.stringify({ name: nextName.trim() }),
    });
    loadViews();
  };

  const browseForFolder = async () => {
    setError("");
    try {
      const result = await callApi("/api/browse-folder", {
        method: "POST",
        body: JSON.stringify({ start_path: chromaPath || "." }),
      });
      if (!result.selected_path) return;
      setChromaPath(result.resolved_path || result.selected_path);
      setPathValid(Boolean(result.valid));
      setPathMessage(result.message || "");
    } catch (err) {
      setError(`Folder picker failed: ${err.message}`);
    }
  };

  const hasInvalidPath = !pathValid;

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
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">RS</div>
          <div>
            <h1>RAGScope</h1>
            <span>RAG quality workbench</span>
          </div>
        </div>

        {["Search", "Audit", "View", "Saved", "ChromaDB"].map((section) => (
          <section className={`accordion ${activeSection === section ? "open" : ""}`} key={section}>
            <button type="button" className="accordion-title" onClick={() => setActiveSection(section)}>
              <span>{section}</span>
              <span>{activeSection === section ? "−" : "+"}</span>
            </button>
            {activeSection === section && (
              <div className="accordion-body">
                {section === "Search" && (
                  <>
                    <label>
                      Text search
                      <input
                        value={prefs.textSearch}
                        onChange={(event) => {
                          updatePref("textSearch", event.target.value);
                          setHighlightedIds([]);
                          setAnalysisResult(null);
                        }}
                        placeholder="Filter visible chunks"
                      />
                    </label>
                    <label>
                      Semantic search
                      <textarea
                        value={prefs.semanticSearch}
                        onChange={(event) => {
                          updatePref("semanticSearch", event.target.value);
                          setAnalysisResult(null);
                        }}
                        placeholder="Find nearest chunks by meaning"
                      />
                    </label>
                    <label>
                      Top K
                      <input type="number" min="1" max="100" value={prefs.semanticTopK} onChange={(event) => updatePref("semanticTopK", Number(event.target.value))} />
                    </label>
                    <button type="button" className="primary" onClick={handleSemanticSearch} disabled={!prefs.semanticSearch.trim() || !selectedCollection || semanticLoading}>
                      {semanticLoading && <span className="button-spinner" aria-hidden="true" />}
                      {semanticLoading ? "Searching..." : "Run Semantic Search"}
                    </button>
                    <button type="button" onClick={handleRetrievalExperiment} disabled={!prefs.semanticSearch.trim() || !selectedCollection || retrievalLoading}>
                      {retrievalLoading && <span className="button-spinner" aria-hidden="true" />}
                      {retrievalLoading ? "Scoring..." : "Experiment: Score Results"}
                    </button>
                    <button type="button" onClick={compareRetrievalModes} disabled={!prefs.semanticSearch.trim() || !selectedCollection || compareLoading}>
                      {compareLoading && <span className="button-spinner" aria-hidden="true" />}
                      {compareLoading ? "Comparing..." : "Compare Retrieval Modes"}
                    </button>
                    <button type="button" onClick={clearSelections}>Clear Selection</button>
                    {!!hierarchyOptions.length && (
                      <div className="hierarchy-filter">
                        <div className="filter-heading">Hierarchy Levels</div>
                        {hierarchyOptions.map((option) => (
                          <label className="check hierarchy-check" key={option.level}>
                            <input
                              type="checkbox"
                              checked={selectedHierarchyLevels.has(option.level)}
                              onChange={(event) => {
                                const next = new Set(selectedHierarchyLevels);
                                if (event.target.checked) {
                                  next.add(option.level);
                                } else {
                                  next.delete(option.level);
                                }
                                const allSelected = hierarchyOptions.every((item) => next.has(item.level));
                                updatePref("hierarchyLevels", allSelected ? null : [...next]);
                                setHighlightedIds([]);
                                setAnalysisResult(null);
                              }}
                            />
                            <span>{option.label}</span>
                            <span className="count">{option.count.toLocaleString()}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </>
                )}
                {section === "Audit" && (
                  <>
                    <label>
                      Audit preset
                      <select value={auditPreset} onChange={(event) => setAuditPreset(event.target.value)}>
                        <option>Quick Scan</option>
                        <option>Standard Audit</option>
                        <option>Retrieval Benchmark</option>
                        <option>Metadata / Hierarchy Only</option>
                      </select>
                    </label>
                    <label>
                      Scope
                      <select value={auditScope} onChange={(event) => setAuditScope(event.target.value)}>
                        <option>Loaded Collection</option>
                        <option>Current Filters</option>
                      </select>
                    </label>
                    <label>
                      Seed queries
                      <textarea value={auditQueries} onChange={(event) => setAuditQueries(event.target.value)} />
                    </label>
                  <div className="button-row">
                      <button
                        type="button"
                        className="tiny-button"
                        title="Ask the configured LLM to generate a reviewable batch of audit seed queries from loaded corpus samples."
                        onClick={generateAuditQueries}
                        disabled={llmAuditSettings.provider === "Disabled" || queryGenerationLoading || !sourceRows.length}
                      >
                        {queryGenerationLoading && <span className="button-spinner" aria-hidden="true" />}
                        {queryGenerationLoading ? "Generating..." : "Generate"}
                      </button>
                      <button type="button" className="tiny-button" title="Save the current audit query batch as portable JSON for repeatable testing." onClick={exportAuditQueries}>Save</button>
                      <button type="button" className="tiny-button" title="Load a previously saved audit query JSON batch so the same test can be rerun." onClick={() => queryImportRef.current?.click()}>Load</button>
                    </div>
                    <input ref={queryImportRef} type="file" accept="application/json,.json" className="hidden-file" onChange={importAuditQueries} />
                    <label>
                      LLM provider
                      <select value={llmAuditSettings.provider} onChange={(event) => updateLlmAuditSetting("provider", event.target.value)}>
                        <option>Disabled</option>
                        <option>LM Studio</option>
                        <option>OpenAI-compatible URL</option>
                      </select>
                    </label>
                    {llmAuditSettings.provider !== "Disabled" && (
                      <>
                        <label>
                          OpenAI-compatible base URL
                          <input
                            value={llmAuditSettings.baseUrl}
                            onChange={(event) => updateLlmAuditSetting("baseUrl", event.target.value)}
                            onBlur={refreshLlmModels}
                            placeholder="http://127.0.0.1:1234/v1"
                          />
                        </label>
                        <label>
                          Model
                          <div className="model-row">
                            <input
                              list="llm-model-options"
                              value={llmAuditSettings.model}
                              onChange={(event) => updateLlmAuditSetting("model", event.target.value)}
                              placeholder="Select or type a model name"
                            />
                            <button type="button" className="icon-button" onClick={refreshLlmModels} disabled={llmModelsLoading || !llmAuditSettings.baseUrl.trim()} title="Refresh available models">
                              {llmModelsLoading ? "..." : "↻"}
                            </button>
                          </div>
                          <datalist id="llm-model-options">
                            {llmModelNames.map((name) => <option value={name} key={name} />)}
                          </datalist>
                          <small>
                            {llmModelDetails[llmAuditSettings.model]?.context_length
                              ? `Reported context: ${llmModelDetails[llmAuditSettings.model].context_length.toLocaleString()} tokens`
                              : "Reported context: unknown"}
                          </small>
                        </label>
                        <label>
                          API key
                          <input type="password" value={llmAuditSettings.apiKey} onChange={(event) => updateLlmAuditSetting("apiKey", event.target.value)} placeholder="Optional for LM Studio" />
                        </label>
                        <label className="check">
                          <input type="checkbox" checked={llmAuditSettings.limitContext} onChange={(event) => updateLlmAuditSetting("limitContext", event.target.checked)} />
                          Limit LLM context to metadata/previews/retrieval summaries
                        </label>
                      </>
                    )}
                    <button type="button" className="primary" onClick={runAudit} disabled={!sourceRows.length || !selectedCollection || auditLoading}>
                      {auditLoading && <span className="button-spinner" aria-hidden="true" />}
                      {auditLoading ? "Running Audit..." : "Run RAG Quality Audit"}
                    </button>
                    <button type="button" onClick={() => setWorkspaceMode("Audit Report")} disabled={!auditReport}>Show Audit Report</button>
                    <div className="saved-list">
                      {savedAudits.slice(0, 5).map((report) => (
                        <div className="saved-item" key={report.id}>
                          <button type="button" onClick={() => {
                            setAuditReport(report);
                            setWorkspaceMode("Audit Report");
                          }}>
                            {report.collection} · {report.scores?.overall ?? "n/a"}
                          </button>
                          <button type="button" className="danger" onClick={() => setSavedAudits((current) => current.filter((item) => item.id !== report.id))}>Delete</button>
                        </div>
                      ))}
                    </div>
                  </>
                )}
                {section === "View" && (
                  <>
                    <label>
                      Dimensions
                      <select value={prefs.dimensions} onChange={(event) => updatePref("dimensions", Number(event.target.value))}>
                        <option value={2}>2D</option>
                        <option value={3}>3D</option>
                      </select>
                    </label>
                    <label>
                      Reduction
                      <select value={prefs.reductionMethod} onChange={(event) => updatePref("reductionMethod", event.target.value)}>
                        <option>UMAP</option>
                        <option>PCA</option>
                      </select>
                    </label>
                    <label>
                      Clustering
                      <select value={prefs.clusteringMethod} onChange={(event) => updatePref("clusteringMethod", event.target.value)}>
                        <option>Auto</option>
                        <option>HDBSCAN</option>
                        <option>KMeans</option>
                        <option>None</option>
                      </select>
                    </label>
                    <label>
                      KMeans clusters
                      <input type="number" min="2" max="80" value={prefs.clusterCount} onChange={(event) => updatePref("clusterCount", Number(event.target.value))} />
                    </label>
                    <label>
                      HDBSCAN min size
                      <input type="number" min="2" max="100" value={prefs.minClusterSize} onChange={(event) => updatePref("minClusterSize", Number(event.target.value))} />
                    </label>
                    <label>
                      Popup Delay
                      <input type="number" min="0" max="5" step="0.1" value={prefs.popupDelay} onChange={(event) => updatePref("popupDelay", Number(event.target.value))} />
                    </label>
                    <label className="check">
                      <input type="checkbox" checked={prefs.hoverEnabled} onChange={(event) => updatePref("hoverEnabled", event.target.checked)} />
                      Enable point popups
                    </label>
                    <button type="button" className="primary" onClick={loadDataset} disabled={!selectedCollection || !pathValid || loading}>Recompute View</button>
                  </>
                )}
                {section === "Saved" && (
                  <>
                    <label>
                      View name
                      <input value={viewName} onChange={(event) => setViewName(event.target.value)} placeholder="Investigation name" />
                    </label>
                    <label>
                      Description
                      <textarea value={viewDescription} onChange={(event) => setViewDescription(event.target.value)} placeholder="What this view captures" />
                    </label>
                    <button type="button" className="primary" onClick={saveView} disabled={!viewName.trim()}>Save Current View</button>
                    <div className="saved-list">
                      {savedViews.map((view) => (
                        <div className="saved-item" key={view.filename}>
                          <button
                            type="button"
                            title="Left-click to load. Right-click to rename."
                            onClick={() => applySavedView(view)}
                            onContextMenu={(event) => {
                              event.preventDefault();
                              renameView(view);
                            }}
                          >
                            {view.name || view.filename}
                          </button>
                          <button type="button" className="danger" onClick={() => deleteView(view.filename)}>Delete</button>
                        </div>
                      ))}
                    </div>
                  </>
                )}
                {section === "ChromaDB" && (
                  <div className={hasInvalidPath ? "path-warning" : ""}>
                    <label>
                      ChromaDB Path
                      <div className="path-row">
                        <input
                          value={chromaPath}
                          onChange={(event) => setChromaPath(event.target.value)}
                          onBlur={refreshCollections}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") {
                              event.currentTarget.blur();
                              refreshCollections();
                            }
                          }}
                        />
                        <button type="button" className="icon-button" title="Browse for a local ChromaDB folder" onClick={browseForFolder}>...</button>
                      </div>
                    </label>
                    <div className={`path-status ${pathValid ? "ok" : "bad"}`}>{pathChecking ? "Checking path..." : pathMessage || (pathValid ? "Path is valid" : "Path has not been validated")}</div>
                    <button type="button" className="primary" onClick={refreshCollections}>Refresh Collections</button>
                    <label>
                      Collection
                      <select value={selectedCollection} onChange={(event) => setSelectedCollection(event.target.value)} disabled={!collections.length}>
                        {collections.map((name) => <option key={name} value={name}>{name}</option>)}
                      </select>
                    </label>
                    <label>
                      Max load
                      <input type="number" min="100" max="100000" step="100" value={prefs.maxLoad} onChange={(event) => updatePref("maxLoad", Number(event.target.value))} />
                    </label>
                    <label className="check">
                      <input type="checkbox" checked={prefs.sampling} onChange={(event) => updatePref("sampling", event.target.checked)} />
                      Sample large collections
                    </label>
                  </div>
                )}
              </div>
            )}
          </section>
        ))}
        <button
          ref={chartWakeButtonRef}
          type="button"
          tabIndex={-1}
          aria-hidden="true"
          className={chartWakeButtonVisible ? "chart-wake-button armed" : "chart-wake-button"}
          data-chart-wake-pulse={chartWakePulse}
          onClick={handleChartWakeClick}
        >
          Wake chart
        </button>
      </aside>

      <main className="workspace" ref={mainRef}>
        <div className="work-main">
          <header className="toolbar">
            <div>
              <strong className="db-title">
                {selectedCollection || "No collection selected"}
                {(loading || pathChecking) && <span className="spinner" aria-label="Backend processing" />}
              </strong>
              <span>{tableFilteredRows.length.toLocaleString()} table rows, {searchResultRows.length.toLocaleString()} search results of {sourceRows.length.toLocaleString()} chunks</span>
            </div>
            <div className="toolbar-actions">
              {loading && <span className="loading">Loading...</span>}
              {error && (
                <button type="button" className="error-text" title="Click to view and copy the full message" onClick={() => setMessageModal({ title: "Message", text: error })}>
                  {short(error, 160)}
                </button>
              )}
            </div>
          </header>
          <div className="pipeline-ribbon">
            <span><strong>{pipelineSummary.loaded.toLocaleString()}</strong> loaded</span>
            <span><strong>{pipelineSummary.visible.toLocaleString()}</strong> visible</span>
            <span><strong>{pipelineSummary.clusters.toLocaleString()}</strong> clusters</span>
            <span><strong>{pipelineSummary.levels.toLocaleString()}</strong> levels</span>
            <span><strong>{pipelineSummary.speakers.toLocaleString()}</strong> speakers</span>
            <span className={pipelineSummary.ranked ? "hot" : ""}><strong>{pipelineSummary.ranked.toLocaleString()}</strong> ranked</span>
            <span className={pipelineSummary.orphans ? "warn" : ""}><strong>{pipelineSummary.orphans.toLocaleString()}</strong> orphans</span>
          </div>
          <div className="workspace-switch">
            {["Explore", "Audit Report"].map((mode) => (
              <button type="button" key={mode} className={workspaceMode === mode ? "active" : ""} onClick={() => setWorkspaceMode(mode)} disabled={mode === "Audit Report" && !auditReport}>
                {mode}
              </button>
            ))}
          </div>
          {workspaceMode === "Explore" ? (
            <>
          <section className="chart-panel" onMouseLeave={handleChartMouseLeave} onMouseUp={selectHoveredPoint}>
            {plotData.length ? (
              <Plot
                key={`${prefs.dimensions}-${selectedCollection}`}
                data={plotData}
                layout={plotLayout}
                revision={selectionRevision}
                config={{ responsive: true, scrollZoom: true, displaylogo: false, modeBarButtonsToRemove: ["toImage"] }}
                className="plot"
                useResizeHandler
                onInitialized={handlePlotReady}
                onSelected={handlePlotSelected}
                onDeselect={clearSelections}
                onClick={handlePlotClick}
                onHover={handlePlotHover}
                onUnhover={() => {
                  if (hoverResetTimerRef.current) window.clearTimeout(hoverResetTimerRef.current);
                  hoveredPointRef.current = null;
                  setHoverPreview("");
                }}
                onRelayout={(event) => {
                  const dimensionKey = String(prefs.dimensions);
                  const normalizedView = normalizePlotlyRelayout(event, prefs.dimensions);
                  const existingView = plotViewsByDimensionRef.current[dimensionKey] || plotRelayoutRef.current || {};
                  const nextRelayout = mergePlotView(existingView, normalizedView);
                  plotRelayoutRef.current = nextRelayout;
                  plotViewsByDimensionRef.current = { ...plotViewsByDimensionRef.current, [dimensionKey]: nextRelayout };
                  if (event?.dragmode) {
                    setPlotRelayout(nextRelayout);
                    setPlotViewsByDimension(plotViewsByDimensionRef.current);
                    setDragMode(event.dragmode);
                  }
                }}
              />
            ) : (
              <div className="empty-state">
                <h2>No points to display</h2>
                <p>Select a valid ChromaDB path and collection, or clear active filters.</p>
              </div>
            )}
          </section>
          <div className="hover-preview" title="Point preview">
            {hoverPreview}
          </div>
          <div className="table-divider" role="separator" aria-label="Resize table height" onMouseDown={startTableResize}>
            <span />
          </div>
          <section className="table-panel" style={{ height: tableHeight }}>
            <button
              type="button"
              className="clear-table-selection"
              title="Clear table row and chart point selections"
              onClick={clearSelections}
              disabled={!tableSelectedIds.length && !chartSelectedIds.length && !searchActive && selectedCluster === ""}
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
                {visibleTableRows.map((row) => (
                  <tr
                    key={row.id}
                    className={tableSelectedSet.has(String(row.id)) ? "selected-row" : ""}
                    onClick={() => {
                      setInspectedRow(row);
                      const id = String(row.id);
                      setTableSelectedIds((current) => (
                        current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
                      ));
                    }}
                  >
                    <td><span className="swatch" style={{ background: clusterColor(row.cluster, colorMap) }} />{row.cluster}</td>
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
          ) : (
            <section className="audit-workspace">
              {auditReport ? (
                <>
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
                    <button type="button" onClick={() => exportAuditReport("md")}>Export Markdown</button>
                    <button type="button" onClick={() => exportAuditReport("json")}>Export JSON</button>
                    <button type="button" onClick={() => setWorkspaceMode("Explore")}>Return to Explore</button>
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
                              const row = rowById.get(String(item.id));
                              if (row) {
                                setInspectedRow(row);
                                setChartSelectedIds([String(item.id)]);
                                setWorkspaceMode("Explore");
                                setInfoTab("Inspect");
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
                              <button type="button" onClick={() => setMessageModal({ title: "LLM Raw Output", text: auditReport.llm.raw || "" })}>
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
                </>
              ) : (
                <div className="empty-state">
                  <h2>No audit report yet</h2>
                  <p>Open the Audit section in the sidebar and run a deterministic Phase 1 audit.</p>
                </div>
              )}
            </section>
          )}
        </div>

        <div className="right-resizer" role="separator" aria-label="Resize right information panel" onMouseDown={startRightResize} />
        <aside className="info-panel" style={{ width: rightWidth }}>
          <div className="info-tabs">
            {INFO_TABS.map((tab) => (
              <button type="button" key={tab} className={infoTab === tab ? "active" : ""} onClick={() => setInfoTab(tab)}>
                {tab}
              </button>
            ))}
          </div>

          {infoTab === "Inspect" && (
            <section>
              <h2>Inspector</h2>
              {inspectedRow ? (
                <div className="inspector">
                  <div className="badge-row">
                    <span className="badge">{hierarchyLabel(hierarchyLevel(inspectedRow))}</span>
                    <span className="badge">Cluster {inspectedRow.cluster}</span>
                    {selectedQuality?.speakers?.slice(0, 3).map((speaker) => <span className="badge" key={speaker}>{speaker}</span>)}
                    {inspectedRow["meta.episode_date"] || inspectedRow.metadata?.episode_date ? <span className="badge">{inspectedRow["meta.episode_date"] || inspectedRow.metadata?.episode_date}</span> : null}
                  </div>
                  <dl>
                    <dt>ID</dt><dd>{inspectedRow.id}</dd>
                    <dt>Rank</dt><dd>{retrievalRankById.has(String(inspectedRow.id)) ? `#${retrievalRankById.get(String(inspectedRow.id))} · ${retrievalScoreById.get(String(inspectedRow.id))}` : "Not ranked"}</dd>
                    <dt>Level</dt><dd>{hierarchyLabel(hierarchyLevel(inspectedRow))}</dd>
                    <dt>Cluster</dt><dd><span className="swatch" style={{ background: clusterColor(inspectedRow.cluster, colorMap) }} />{inspectedRow.cluster}</dd>
                    <dt>Source</dt><dd>{inspectedRow.source || "Unknown"}</dd>
                    <dt>Title</dt><dd>{inspectedRow.title || "Untitled"}</dd>
                  </dl>
                  <h3>Chunk quality</h3>
                  {selectedQuality ? (
                    <div className="quality-grid">
                      <span><strong>{selectedQuality.textLength.toLocaleString()}</strong><small>chars</small></span>
                      <span><strong>{selectedQuality.tokenEstimate.toLocaleString()}</strong><small>est. tokens</small></span>
                      <span><strong>{selectedQuality.speakerCount}</strong><small>speakers</small></span>
                      <span><strong>{selectedQuality.duration === null ? "n/a" : `${selectedQuality.duration.toFixed(1)}s`}</strong><small>duration</small></span>
                      <span><strong>{selectedQuality.parentCount}</strong><small>parents</small></span>
                      <span><strong>{selectedQuality.childCount}</strong><small>children</small></span>
                      <span><strong>{selectedQuality.parentSimilarity === null ? "n/a" : selectedQuality.parentSimilarity.toFixed(3)}</strong><small>parent fit</small></span>
                      <span><strong>{selectedQuality.nearest ? selectedQuality.nearest.similarity.toFixed(3) : "n/a"}</strong><small>nearest fit</small></span>
                    </div>
                  ) : <p className="muted">Quality metrics are available after a dataset is loaded.</p>}
                  <h3>Why this result?</h3>
                  {whyResult ? (
                    <div className="why-panel">
                      <p className="muted">Transparent non-LLM diagnostics for the selected chunk.</p>
                      <div className="tag-list">
                        {(whyResult.overlap.length ? whyResult.overlap : ["no direct query term overlap"]).map((term) => <span className="tag" key={term}>{term}</span>)}
                      </div>
                      <dl>
                        <dt>Score</dt><dd>{whyResult.score === undefined ? "Not in current ranked run" : `${whyResult.score} (#${whyResult.rank})`}</dd>
                        <dt>Topic</dt><dd>{whyResult.topic || "No topic label"}</dd>
                        <dt>Location</dt><dd>{whyResult.level} · cluster {whyResult.cluster}</dd>
                        <dt>Neighbor</dt><dd>{whyResult.nearest ? `${whyResult.nearest.row.id} · ${whyResult.nearest.similarity.toFixed(3)}` : "Not computed"}</dd>
                      </dl>
                      {!!whyResult.metadataOverlaps.length && (
                        <table className="mini-table"><tbody>{whyResult.metadataOverlaps.map(([key, value]) => (
                          <tr key={key}><td>{key}</td><td>{String(value)}</td></tr>
                        ))}</tbody></table>
                      )}
                    </div>
                  ) : <p className="muted">Select a search result to explain score, context, and neighborhood.</p>}
                  <h3>Chunk text</h3>
                  <pre>{inspectorLoading ? "Loading chunk text..." : inspectedDocument?.document || inspectedRow.preview}</pre>
                  <h3>Metadata</h3>
                  <pre>{JSON.stringify(inspectedDocument?.metadata || inspectedRow.metadata || {}, null, 2)}</pre>
                </div>
              ) : (
                <p className="muted">Click a point or row to inspect a chunk.</p>
              )}
            </section>
          )}

          {infoTab === "Analyze" && (
            <>
              <section>
                <div className="section-heading-row">
                  <h2>Selection Analysis</h2>
                  <button type="button" className="compact-button" onClick={() => handleAnalyzeSelection()} disabled={!canAnalyzeSelection || analysisLoading}>
                    {analysisLoading ? "Analyzing..." : explicitSelectedIds.length ? "Analyze" : activeSearchIds.length ? "Analyze Results" : selectedCluster !== "" ? "Analyze Cluster" : "Analyze"}
                  </button>
                </div>
                {analysisResult ? (
                  <div className="analysis-panel">
                    <p className="muted">{analysisResult.selected_count} selected of {analysisResult.total_count} chunks ({analysisResult.coverage_percent}%).</p>
                    <h3>Distinctive Terms</h3>
                    <div className="tag-list">
                      {(analysisResult.keywords || []).slice(0, 12).map((item) => <span className="tag" key={item.term}>{item.term}</span>)}
                    </div>
                    <h3>Shared Signals</h3>
                    {(analysisResult.common_metadata || []).length ? (
                      <table className="mini-table"><tbody>{(analysisResult.common_metadata || []).slice(0, 8).map((item) => (
                        <tr key={`${item.field}-${item.value}`}><td>{item.field}</td><td>{item.value}</td><td>{item.selected_percent}%</td></tr>
                      ))}</tbody></table>
                    ) : <p className="muted">No high-value metadata commonality found.</p>}
                    <h3>Dominant Topics</h3>
                    <ul className="plain-list">{(analysisResult.dominant_topics || []).slice(0, 6).map((item) => <li key={item.value}>{item.value || "Untitled"} ({item.selected_count})</li>)}</ul>
                    <h3>Date Ranges</h3>
                    <ul className="plain-list">
                      {(analysisResult.date_ranges || []).map((item) => <li key={item.field}>{item.field}: {item.start} to {item.end}</li>)}
                      {!(analysisResult.date_ranges || []).length && <li>No date-like selection fields found.</li>}
                    </ul>
                    <h3>Representative Chunks</h3>
                    <div className="representative-list">
                      {(analysisResult.representative_chunks || []).slice(0, 5).map((item) => (
                        <button type="button" key={item.id} onClick={() => {
                          const row = rowById.get(String(item.id));
                          if (row) setInspectedRow(row);
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
                  <button type="button" className={selectedCluster === "" ? "cluster active" : "cluster"} onClick={() => setSelectedCluster("")}>
                    <span className="swatch neutral" />All clusters
                  </button>
                  {clusterRows.map((topic) => (
                    <button type="button" key={topic.cluster} className={String(selectedCluster) === String(topic.cluster) ? "cluster active" : "cluster"} onClick={() => setSelectedCluster(String(topic.cluster))}>
                      <span className="swatch" style={{ background: topic.color }} />
                      <span><strong>{topic.label}</strong><small>Cluster {topic.cluster} · {topic.count} chunks</small></span>
                      <span className="cluster-analyze" title="Analyze this cluster topic" onClick={(event) => {
                        event.stopPropagation();
                        const clusterIds = sourceRows.filter((row) => String(row.cluster) === String(topic.cluster)).map((row) => String(row.id));
                        setSelectedCluster(String(topic.cluster));
                        setChartSelectedIds([]);
                        setTableSelectedIds([]);
                        handleAnalyzeSelection(clusterIds);
                      }}>Analyze</span>
                    </button>
                  ))}
                </div>
              </section>
              <section>
                <h2>Outliers & Orphans</h2>
                <p className="muted">Outliers use projected nearest-neighbor distance; orphans are nodes whose parent id is not present in the loaded dataset.</p>
                <div className="quality-list">
                  {outlierRows.slice(0, 8).map((item) => (
                    <button type="button" key={item.row.id} onClick={() => {
                      setInspectedRow(item.row);
                      setChartSelectedIds([String(item.row.id)]);
                      setInfoTab("Inspect");
                    }}>
                      <strong>{item.orphan ? "Orphan + outlier" : "Outlier"} · {item.nearest.similarity.toFixed(3)} nearest fit</strong>
                      <small>{hierarchyLabel(hierarchyLevel(item.row))}: {short(item.row.preview, 120)}</small>
                    </button>
                  ))}
                  {!outlierRows.length && <p className="muted">No outlier candidates available.</p>}
                </div>
                {!!orphanRows.length && (
                  <>
                    <h3>Hierarchy Orphans</h3>
                    <div className="quality-list">
                      {orphanRows.slice(0, 6).map((row) => (
                        <button type="button" key={row.id} onClick={() => {
                          setInspectedRow(row);
                          setChartSelectedIds([String(row.id)]);
                          setInfoTab("Inspect");
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
          )}

          {infoTab === "Retrieval" && (
            <section>
              <div className="section-heading-row">
                <h2>Retrieval Experiment</h2>
                <div className="button-row">
                  <button type="button" className="compact-button" onClick={handleRetrievalExperiment} disabled={!prefs.semanticSearch.trim() || retrievalLoading}>
                    {retrievalLoading ? "Scoring..." : "Run"}
                  </button>
                  <button type="button" className="compact-button" onClick={saveRetrievalRun} disabled={!retrievalResult}>Save</button>
                  <button type="button" className="compact-button" onClick={exportRetrievalReport} disabled={!retrievalResult}>Export</button>
                </div>
              </div>
              <p className="muted">Scores the current filtered candidate set against the semantic query and overlays ranked results on the chart.</p>
              {retrievalResult ? (
                <div className="retrieval-panel">
                  <div className="metric-grid">
                    <span><strong>{retrievalResult.candidate_count?.toLocaleString?.() || 0}</strong><small>candidates</small></span>
                    <span><strong>{(retrievalResult.results || []).length}</strong><small>ranked</small></span>
                    <span><strong>{retrievalResult.embedding_dim}</strong><small>dimensions</small></span>
                  </div>
                  <h3>Score Distribution</h3>
                  <div className="histogram">
                    {(retrievalResult.histogram || []).map((bucket, index) => {
                      const maxCount = Math.max(...(retrievalResult.histogram || []).map((item) => item.count), 1);
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
                    {(retrievalResult.results || []).map((item) => {
                      const row = rowById.get(String(item.id));
                      return (
                        <button type="button" key={item.id} onClick={() => {
                          if (row) setInspectedRow(row);
                          setChartSelectedIds([String(item.id)]);
                          setInfoTab("Inspect");
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
                <textarea value={retrievalNotes} onChange={(event) => setRetrievalNotes(event.target.value)} placeholder="Observations to save with this retrieval run" />
              </label>
              <h3>Saved Retrieval Runs</h3>
              <div className="saved-run-list">
                {savedRuns.slice(0, 8).map((run) => (
                  <div className="saved-run" key={run.id}>
                    <button type="button" onClick={() => loadRetrievalRun(run)}>
                      <strong>{run.name}</strong>
                      <small>{new Date(run.timestamp).toLocaleString()} · {run.ids.length} results</small>
                    </button>
                    <button type="button" className="danger compact-button" onClick={() => setSavedRuns((current) => current.filter((item) => item.id !== run.id))}>Delete</button>
                  </div>
                ))}
                {!savedRuns.length && <p className="muted">Saved runs preserve query, filters, top-k, returned ids, scores, and timestamp for later comparison.</p>}
              </div>
            </section>
          )}

          {infoTab === "Compare" && (
            <section>
              <div className="section-heading-row">
                <h2>Compare Retrieval Modes</h2>
                <button type="button" className="compact-button" onClick={compareRetrievalModes} disabled={!prefs.semanticSearch.trim() || compareLoading}>
                  {compareLoading ? "Comparing..." : "Compare"}
                </button>
              </div>
              <p className="muted">Runs the same query across hierarchy-based candidate pools so you can see whether summaries, claims, or leaf chunks dominate retrieval.</p>
              {compareResult ? (
                <div className="compare-grid">
                  {compareResult.map((mode) => (
                    <div className="compare-card" key={mode.name}>
                      <h3>{mode.name}</h3>
                      <p className="muted">{mode.candidateCount.toLocaleString()} candidates</p>
                      {(mode.result?.results || []).slice(0, 5).map((item) => {
                        const row = rowById.get(String(item.id));
                        return (
                          <button type="button" key={`${mode.name}-${item.id}`} onClick={() => {
                            setRetrievalResult(mode.result);
                            setHighlightedIds((mode.result?.ids || []).map(String));
                            if (row) setInspectedRow(row);
                            setInfoTab("Inspect");
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
          )}

          {infoTab === "Hierarchy" && (
            <section>
              <h2>Result Path</h2>
              <p className="muted">Shows the selected result in its RAG hierarchy, from higher-level summary nodes down to the inspected chunk when parent metadata is available.</p>
              {hierarchyTrace.length ? (
                <div className="path-trace">
                  {hierarchyTrace.map((row, index) => (
                    <button type="button" key={`${row.id}-${index}`} onClick={() => {
                      setInspectedRow(row);
                      setInfoTab("Inspect");
                    }}>
                      <span className="path-level">{hierarchyLabel(hierarchyLevel(row))}</span>
                      <strong>{row.title || row.source || row.id}</strong>
                      <small>{short(row.preview, 150)}</small>
                    </button>
                  ))}
                </div>
              ) : <p className="muted">Select a point, table row, or retrieval result to trace its parent path.</p>}
            </section>
          )}
        </aside>
      </main>
      {messageModal && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setMessageModal(null)}>
          <div className="message-modal" role="dialog" aria-modal="true" aria-label={messageModal.title} onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h2>{messageModal.title}</h2>
              <div className="button-row">
                <button type="button" className="icon-button" title="Copy message to clipboard" onClick={copyModalText}>⧉</button>
                <button type="button" className="icon-button" title="Close" onClick={() => setMessageModal(null)}>×</button>
              </div>
            </div>
            <pre>{messageModal.text}</pre>
          </div>
        </div>
      )}
      <div className="toast-stack" aria-live="polite" aria-relevant="additions">
        {toasts.map((toast) => (
          <div className={`toast ${toast.type}`} key={toast.id}>
            <div>
              <strong>{toast.title}</strong>
              <button type="button" onClick={() => setMessageModal({ title: toast.title, text: toast.message })}>
                {short(toast.message, 180)}
              </button>
            </div>
            <button type="button" className="toast-dismiss" title="Dismiss notification" onClick={() => dismissToast(toast.id)}>×</button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
