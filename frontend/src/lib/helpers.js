import { HIERARCHY_LABELS, HIERARCHY_ORDER } from "./constants";

export function loadJson(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

export function short(value, length = 180) {
  const text = String(value || "");
  return text.length <= length ? text : `${text.slice(0, length - 1)}...`;
}

export function clusterColor(cluster, colorMap) {
  return colorMap?.[String(cluster)] || "#8ea0ff";
}

export function hierarchyLevel(row) {
  return String(row?.["meta.level"] || row?.metadata?.level || row?.level || "unknown");
}

export function hierarchyLabel(level) {
  return HIERARCHY_LABELS[level] || String(level).replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function hierarchyRank(level) {
  if (HIERARCHY_ORDER[level] !== undefined) return HIERARCHY_ORDER[level];
  const summaryMatch = String(level).match(/^summary_(\d+)$/);
  if (summaryMatch) return 10 - Number(summaryMatch[1]);
  return 50;
}

export function rowNodeId(row) {
  return String(row?.["meta.node_id"] || row?.metadata?.node_id || row?.id || "");
}

export function rowParentId(row) {
  return String(row?.["meta.parent_id"] || row?.metadata?.parent_id || "");
}

export function retrievalRankColor(rank) {
  if (rank <= 1) return "#ff5a5f";
  if (rank <= 5) return "#ff9f1c";
  if (rank <= 12) return "#ffd166";
  return "#b8f2e6";
}

export function numericMeta(row, keys) {
  for (const key of keys) {
    const value = row?.[`meta.${key}`] ?? row?.metadata?.[key] ?? row?.[key];
    const number = Number(value);
    if (Number.isFinite(number)) return number;
  }
  return null;
}

export function splitSpeakerValues(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  return String(value).split(/[,;|]/).map((item) => item.trim()).filter(Boolean);
}

export function keywordTokens(text) {
  const stop = new Set(["about", "after", "again", "also", "because", "been", "being", "from", "have", "into", "like", "more", "much", "only", "over", "said", "that", "their", "them", "then", "there", "these", "they", "this", "very", "were", "what", "when", "where", "which", "with", "would", "your"]);
  return String(text || "").toLowerCase().match(/[a-z][a-z0-9']{2,}/g)?.filter((token) => !stop.has(token)) || [];
}

export function percent(value, total) {
  return total ? Math.round((value / total) * 1000) / 10 : 0;
}

export function scoreFromPercent(value) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function downloadText(filename, text, type = "text/plain;charset=utf-8") {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
