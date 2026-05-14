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

export function sortModelsForDisplay(models) {
  return [...(Array.isArray(models) ? models : [])].sort((a, b) => {
    const favoriteDelta = Number(Boolean(b?.favorite)) - Number(Boolean(a?.favorite));
    if (favoriteDelta !== 0) return favoriteDelta;
    return String(a?.name || "").localeCompare(String(b?.name || ""));
  });
}
