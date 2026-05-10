export const RUNTIME_CONFIG = window.RAGSCOPE_CONFIG || window.CHROMADB_VISUALIZER_CONFIG || {};
export const API_BASE = RUNTIME_CONFIG.apiBase || "http://127.0.0.1:8765";

export const TABLE_HEIGHT_KEY = "ragscope.react.tableHeight";
export const RIGHT_WIDTH_KEY = "ragscope.react.rightWidth";
export const PATH_KEY = "ragscope.react.chromaPath";
export const VIEW_PREFS_KEY = "ragscope.react.viewPrefs";
export const SAVED_RUNS_KEY = "ragscope.react.savedRetrievalRuns";
export const SAVED_AUDITS_KEY = "ragscope.react.savedAudits";
export const LLM_AUDIT_SETTINGS_KEY = "ragscope.react.llmAuditSettings";
export const MAX_ANALYSIS_IDS = 10000;

export const DEFAULT_PREFS = {
  reductionMethod: "UMAP",
  dimensions: 2,
  clusteringMethod: "Auto",
  clusterCount: 8,
  minClusterSize: 8,
  maxLoad: 5000,
  sampling: true,
  colorMode: "cluster",
  textSearch: "",
  semanticSearch: "",
  semanticTopK: 12,
  hoverEnabled: true,
  popupDelay: 1,
  hierarchyLevels: null,
};

export const HIERARCHY_LABELS = {
  episode: "Episode Thesis",
  position: "Claim / Position Cards",
  summary_4: "Broad Summaries",
  summary_3: "Mid-Level Summaries",
  summary_2: "Focused Summaries",
  summary_1: "Detailed Summaries",
  leaf: "Transcript Leaf Chunks",
  unknown: "Unknown Level",
};

export const HIERARCHY_ORDER = {
  episode: 0,
  position: 1,
  summary_4: 2,
  summary_3: 3,
  summary_2: 4,
  summary_1: 5,
  leaf: 6,
  unknown: 99,
};

export const INFO_TABS = ["Inspect", "Analyze", "Retrieval", "Compare", "Hierarchy"];

export const DEFAULT_AUDIT_QUERIES = [
  "What are the central claims or arguments?",
  "What topics are discussed most often?",
  "What does the speaker think about institutions and power?",
  "Which episodes contain the strongest summary of the viewpoint?",
  "What controversial or distinctive positions are represented?",
];

export const DEFAULT_LLM_AUDIT_SETTINGS = {
  provider: "Disabled",
  baseUrl: "http://127.0.0.1:1234/v1",
  model: "",
  apiKey: "",
  limitContext: false,
};
