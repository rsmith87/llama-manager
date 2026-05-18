export function nodeSearchText(node) {
  return [node.name, node.url, node.agent_config_source, node.controller_config_source]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function filterNodes(nodes, { query = "", status = "", registration = "" } = {}) {
  const normalizedQuery = query.trim().toLowerCase();
  return nodes.filter((node) => {
    const okQuery = !normalizedQuery || nodeSearchText(node).includes(normalizedQuery);
    const okStatus = !status || (status === "reachable" ? Boolean(node.reachable) : !node.reachable);
    const okRegistration = !registration || node.registration === registration;
    return okQuery && okStatus && okRegistration;
  });
}

export function nodeSummary(nodes) {
  const reachable = nodes.filter((node) => node.reachable).length;
  const models = nodes.reduce((sum, node) => sum + (Array.isArray(node.models) ? node.models.length : 0), 0);
  return { reachable, total: nodes.length, models };
}

export function mergeNodeInventory(nodes, nodeModels) {
  const byName = new Map();
  for (const node of Array.isArray(nodes) ? nodes : []) {
    if (node?.name) byName.set(node.name, { ...node, reachable: false, models: [] });
  }
  for (const node of Array.isArray(nodeModels) ? nodeModels : []) {
    if (!node?.name) continue;
    byName.set(node.name, { ...(byName.get(node.name) || {}), ...node });
  }
  return Array.from(byName.values()).sort((a, b) => String(a.name).localeCompare(String(b.name)));
}

export function suggestedGgufModelName(file) {
  return String(file?.name || file?.model_dir || "").trim();
}

export const PROMPT_TEMPLATE_OPTIONS = [
  { value: "", label: "Auto / server default" },
  { value: "llama3", label: "Llama 3" },
  { value: "llama-3", label: "Llama 3 (alias)" },
  { value: "chatml", label: "ChatML" },
  { value: "qwen", label: "Qwen (ChatML)" },
  { value: "gemma", label: "Gemma" },
  { value: "gpt-oss", label: "GPT-OSS (ChatML)" },
  { value: "gptoss", label: "GPTOSS (ChatML alias)" },
];

export function suggestedPromptTemplate(file) {
  const text = [file?.name, file?.model_dir, file?.filename, file?.path]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  if (text.includes("gpt-oss")) return "gpt-oss";
  if (text.includes("llama-3") || text.includes("llama3")) return "llama3";
  if (text.includes("gemma")) return "gemma";
  if (text.includes("qwen")) return "qwen";
  if (text.includes("chatml")) return "chatml";
  return "";
}

export function sortModelsForDisplay(models) {
  return [...(Array.isArray(models) ? models : [])].sort((a, b) => {
    const favoriteDelta = Number(Boolean(b?.favorite)) - Number(Boolean(a?.favorite));
    if (favoriteDelta !== 0) return favoriteDelta;
    return String(a?.name || "").localeCompare(String(b?.name || ""));
  });
}

export function nodeEditFormDefaults(node) {
  return {
    name: String(node?.name || ""),
    url: String(node?.url || ""),
    api_key: "",
    verify_tls: node?.verify_tls ?? true,
  };
}

export function nodeEditMarkup(node, { compact } = {}) {
  if (compact) return "";
  return `<button class="primary node-edit-button" type="button" data-edit-node="${escapeAttribute(node?.name || "")}">Edit Node</button>`;
}

function escapeAttribute(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
