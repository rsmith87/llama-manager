import {
  applyTelemetryFromChunk,
  finalizeTelemetry,
} from "/ui/chat_telemetry.js";
import {
  chooseChatSessionToResume,
  buildChatSessionSavePayload,
  isChatSessionReusable,
  nextSelectedChatSessionId,
} from "/ui/chat_sessions.js";
import {
  filterNodes,
  mergeNodeInventory,
  nodeEditFormDefaults,
  nodeEditMarkup,
  nodeSummary,
  sortModelsForDisplay,
  suggestedGgufModelName,
} from "/ui/nodes_view.js?v=nodes-edit-20260515";

const state = {
  health: null,
  localModels: [],
  nodeModels: [],
  conversions: [],
  downloads: [],
  quantizations: [],
  ggufFiles: [],
  chatMessages: [],
  chatPending: false,
  chatAbortController: null,
  lastUserPrompt: "",
  activePage: "dashboard",
  chatCapabilities: null,
  controllerJobs: [],
  controllerStats: null,
  retentionPolicy: null,
  nodesLoadError: "",
  chatSessions: [],
  lastEmbeddingsResult: null,
  kvCapabilities: null,
  auditEvents: [],
  authKeys: [],
  authToken: localStorage.getItem("lm_ui_token") || "",
  authUser: "",
  authRole: "",
  selectedGgufId: null,
  selectedChatSessionId: "",
  logAbortController: null,
};

const CHAT_PRESETS = {
  balanced: { temperature: 0.7, top_p: 1.0, top_k: 40, min_p: 0.0, repeat_penalty: 1.1, seed: -1 },
  deterministic: { temperature: 0.2, top_p: 0.9, top_k: 20, min_p: 0.0, repeat_penalty: 1.05, seed: 42 },
  creative: { temperature: 1.0, top_p: 1.0, top_k: 80, min_p: 0.0, repeat_penalty: 1.0, seed: -1 },
};
const CHAT_PRESET_STORAGE_KEY = "lm_chat_preset";
const ACTIVE_CHAT_SESSION_STORAGE_KEY = "lm_active_chat_session_id";

const $ = (id) => document.getElementById(id);

const ICONS = {
  audit: `<svg viewBox="0 0 24 24" fill="none"><path d="M7 4h10l2 2v14H5V6l2-2Z"/><path d="M8 9h8M8 13h8M8 17h5"/></svg>`,
  chat: `<svg viewBox="0 0 24 24" fill="none"><path d="M5 6.5A3.5 3.5 0 0 1 8.5 3h7A3.5 3.5 0 0 1 19 6.5v4A3.5 3.5 0 0 1 15.5 14H11l-5 4v-4.5A3.5 3.5 0 0 1 5 10.5v-4Z"/><path d="M8.5 8.5h7M8.5 11h4"/></svg>`,
  controller: `<svg viewBox="0 0 24 24" fill="none"><path d="M4 6h16M4 12h16M4 18h16"/><path d="M8 6v4M16 12v4M11 18v2"/></svg>`,
  convert: `<svg viewBox="0 0 24 24" fill="none"><path d="M7 7h10l-3-3M17 17H7l3 3"/><path d="M17 7 7 17"/></svg>`,
  download: `<svg viewBox="0 0 24 24" fill="none"><path d="M12 4v11"/><path d="m8 11 4 4 4-4"/><path d="M5 19h14"/></svg>`,
  cpu: `<svg viewBox="0 0 24 24" fill="none"><rect x="7" y="7" width="10" height="10" rx="2"/><path d="M4 9h3M4 15h3M17 9h3M17 15h3M9 4v3M15 4v3M9 17v3M15 17v3"/></svg>`,
  dashboard: `<svg viewBox="0 0 24 24" fill="none"><path d="M4 13a8 8 0 1 1 16 0"/><path d="m12 13 4-5"/><path d="M7 17h10"/></svg>`,
  embed: `<svg viewBox="0 0 24 24" fill="none"><circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="7" r="2.5"/><circle cx="8" cy="18" r="2.5"/><circle cx="17" cy="17" r="2.5"/><path d="M8 7.5 16 6.5M7 8.5l1 7M10 17.5l5-.5M16.5 9.5l.5 5"/></svg>`,
  gpu: `<svg viewBox="0 0 24 24" fill="none"><rect x="4" y="7" width="13" height="10" rx="2"/><path d="M17 10h3v4h-3M7 10h5v4H7zM8 4v3M13 4v3M8 17v3M13 17v3"/></svg>`,
  library: `<svg viewBox="0 0 24 24" fill="none"><path d="M5 5h14v14H5z"/><path d="M8 5v14M11 8h5M11 12h5M11 16h3"/></svg>`,
  logs: `<svg viewBox="0 0 24 24" fill="none"><path d="M7 4h10l2 2v14H5V6l2-2Z"/><path d="M8 10h8M8 14h8M8 18h5"/></svg>`,
  memory: `<svg viewBox="0 0 24 24" fill="none"><path d="M6 8h12v8H6z"/><path d="M8 6V4M12 6V4M16 6V4M8 20v-2M12 20v-2M16 20v-2M4 10H2M4 14H2M22 10h-2M22 14h-2"/></svg>`,
  menu: `<svg viewBox="0 0 24 24" fill="none"><path d="M4 7h16M4 12h16M4 17h16"/></svg>`,
  modal: `<svg viewBox="0 0 24 24" fill="none"><rect x="5" y="7" width="14" height="10" rx="2"/><path d="M8 7V5h8v2"/></svg>`,
  models: `<svg viewBox="0 0 24 24" fill="none"><path d="M6 8 12 4l6 4v8l-6 4-6-4V8Z"/><path d="m6 8 6 4 6-4M12 12v8"/></svg>`,
  nodes: `<svg viewBox="0 0 24 24" fill="none"><rect x="4" y="4" width="6" height="6" rx="2"/><rect x="14" y="4" width="6" height="6" rx="2"/><rect x="9" y="14" width="6" height="6" rx="2"/><path d="M10 7h4M7 10v2l4 2M17 10v2l-4 2"/></svg>`,
  pulse: `<svg viewBox="0 0 24 24" fill="none"><path d="M3 12h4l2-6 4 12 2-6h6"/></svg>`,
  quant: `<svg viewBox="0 0 24 24" fill="none"><path d="M5 5h14v4H5zM7 9v10M17 9v10"/><path d="M9 14h6M10 18h4"/></svg>`,
  settings: `<svg viewBox="0 0 24 24" fill="none"><path d="M12 8.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Z"/><path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a1 1 0 0 1 0 1.4l-1.2 1.2a1 1 0 0 1-1.4 0l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a1 1 0 0 1-1 1h-1.6a1 1 0 0 1-1-1v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a1 1 0 0 1-1.4 0l-1.2-1.2a1 1 0 0 1 0-1.4l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a1 1 0 0 1-1-1v-1.6a1 1 0 0 1 1-1h.2a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1a1 1 0 0 1 0-1.4l1.2-1.2a1 1 0 0 1 1.4 0l.1.1a1 1 0 0 0 1.1.2 1 1 0 0 0 .6-.9V4a1 1 0 0 1 1-1h1.6a1 1 0 0 1 1 1v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a1 1 0 0 1 1.4 0l1.2 1.2a1 1 0 0 1 0 1.4l-.1.1a1 1 0 0 0-.2 1.1 1 1 0 0 0 .9.6h.2a1 1 0 0 1 1 1v1.6a1 1 0 0 1-1 1h-.2a1 1 0 0 0-.9.6Z"/></svg>`,
};

function hydrateIcons() {
  document.querySelectorAll("[data-icon]").forEach((element) => {
    const icon = ICONS[element.dataset.icon];
    if (!icon) return;
    element.innerHTML = icon;
    element.querySelector("svg")?.setAttribute("stroke-width", "1.8");
    element.querySelector("svg")?.setAttribute("stroke-linecap", "round");
    element.querySelector("svg")?.setAttribute("stroke-linejoin", "round");
  });
}

function openDrawer(id) {
  const drawer = $(id);
  if (!drawer) return;
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
}

function closeDrawer(drawer) {
  if (!drawer) return;
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
}

function openModal(id) {
  const modal = $(id);
  if (!modal) return;
  if (typeof modal.showModal === "function" && !modal.open) {
    modal.showModal();
  }
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

function closeModal(modal) {
  if (!modal) return;
  if (typeof modal.close === "function" && modal.open) {
    modal.close();
  }
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

function openLogModal() {
  openModal("logs-modal");
}

function stopLogStream() {
  if (state.logAbortController) {
    state.logAbortController.abort();
    state.logAbortController = null;
  }
}

function appendLogText(text) {
  if (!text) return;
  const output = $("log-output");
  const nearBottom = output.scrollTop + output.clientHeight >= output.scrollHeight - 40;
  output.textContent += text;
  if (nearBottom) {
    output.scrollTop = output.scrollHeight;
  }
}

async function streamLogsIntoModal({ title, streamPath, fallbackPath, emptyText }) {
  stopLogStream();
  $("log-title").textContent = title;
  $("log-output").textContent = "";
  openLogModal();
  state.logAbortController = new AbortController();
  try {
    const { reader } = await fetchStream(streamPath, {
      method: "GET",
      headers: { Accept: "text/event-stream" },
      signal: state.logAbortController.signal,
    });
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      for (const event of events) {
        const lines = event.split("\n");
        const eventName = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
        if (eventName !== "chunk") continue;
        const dataLine = lines.find((line) => line.startsWith("data:"));
        if (!dataLine) continue;
        const payload = JSON.parse(dataLine.slice(5));
        appendLogText(String(payload.text || ""));
      }
      if (done) break;
    }
  } catch (error) {
    if (error?.name === "AbortError") return;
    const payload = await api(fallbackPath);
    $("log-output").textContent = payload.text || payload.result?.text || emptyText;
  } finally {
    state.logAbortController = null;
  }
}

async function api(path, options = {}) {
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  if (state.authToken) headers["X-UI-Session"] = state.authToken;
  const response = await fetch(path, {
    ...options,
    headers,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return response.json();
}

async function loginUi() {
  const username = ($("auth-username").value || "").trim();
  const apiKey = ($("auth-api-key").value || "").trim();
  if (!username || !apiKey) return showToast("Enter username and API key.");
  const response = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ username, api_key: apiKey }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Login failed");
  }
  const payload = await response.json();
  state.authToken = payload.token;
  state.authUser = payload.username;
  state.authRole = payload.role || "operator";
  localStorage.setItem("lm_ui_token", state.authToken);
  $("auth-user").textContent = `Logged in: ${state.authUser} (${state.authRole})`;
  await writeAuditEvent({ actor: state.authUser, event_type: "auth_login", dry_run: false, target: state.authUser, route: "auth", payload: { role: state.authRole } });
}

async function logoutUi() {
  await writeAuditEvent({ actor: state.authUser || "unknown", event_type: "auth_logout", dry_run: false, target: state.authUser || "unknown", route: "auth", payload: {} });
  try {
    await api("/auth/logout", { method: "POST" });
  } catch (_error) {
    // ignore
  }
  state.authToken = "";
  state.authUser = "";
  localStorage.removeItem("lm_ui_token");
  $("auth-user").textContent = "Not logged in";
}

async function bootstrapAuth() {
  if (!state.authToken) return;
  try {
    const me = await api("/auth/me");
    state.authUser = me.username || "";
    state.authRole = me.role || "operator";
    $("auth-user").textContent = `Logged in: ${state.authUser} (${state.authRole})`;
  } catch (_error) {
    state.authToken = "";
    localStorage.removeItem("lm_ui_token");
    $("auth-user").textContent = "Not logged in";
  }
}

async function fetchStream(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.authToken) headers["X-UI-Session"] = state.authToken;
  const response = await fetch(path, {
    ...options,
    headers,
  });
  if (!response.ok) {
    const text = await response.text();
    const error = new Error(`${response.status} ${response.statusText}: ${text}`);
    error.status = response.status;
    throw error;
  }
  if (!response.body) {
    throw new Error("Streaming response is not supported by this browser.");
  }
  return { reader: response.body.getReader(), response };
}

async function refreshAll() {
  $("refresh-button").disabled = true;
  try {
    state.health = await api("/health");
    renderHealth();

    await refreshControllerData();

    await refreshSection(async () => {
      state.localModels = await api("/models");
      renderLocalModels();
      renderChatModelOptions();
    });

    await refreshSection(async () => {
      state.ggufFiles = await api("/library/ggufs");
      renderGgufLibrary();
    });

    await refreshSection(async () => {
      state.conversions = await api("/conversions/models");
      renderConversions();
    });
    await refreshSection(async () => {
      state.downloads = await api("/downloads/history?limit=200");
      renderDownloads();
    });

    await refreshSection(async () => {
      state.quantizations = await api("/quantizations/files");
      renderQuantizations();
    });

    renderNodes();
    renderNodesPage();
    renderControllerOps();
    await refreshSection(refreshAuditEvents);
    await refreshSection(refreshAuthKeys);
    await refreshSection(refreshChatSessions);
    $("last-updated").textContent = new Date().toLocaleTimeString();
  } catch (error) {
    showToast(error.message);
  } finally {
    $("refresh-button").disabled = false;
  }
}

async function refreshSection(refresher) {
  try {
    await refresher();
  } catch (error) {
    showToast(error.message);
  }
}

async function refreshControllerData() {
  if (state.health?.mode !== "controller") {
    state.nodeModels = [];
    state.controllerJobs = [];
    state.controllerStats = null;
    state.retentionPolicy = null;
    state.nodesLoadError = "";
    return;
  }

  const [nodes, nodeModels, jobs, stats, policy] = await Promise.all([
    api("/nodes").then((result) => {
      state.nodesLoadError = "";
      return result;
    }).catch((error) => {
      state.nodesLoadError = error.message;
      return [];
    }),
    api("/nodes/models").catch(() => []),
    api("/jobs?limit=50").catch(() => []),
    api("/controller/stats").catch(() => null),
    api("/controller/retention-policy").catch(() => null),
  ]);
  state.nodeModels = mergeNodeInventory(nodes, nodeModels);
  state.controllerJobs = jobs;
  state.controllerStats = stats;
  state.retentionPolicy = policy;
  renderNodes();
  renderNodesPage();
  renderControllerOps();
}

async function refreshNodesPageData() {
  try {
    if (!state.health) {
      state.health = await api("/health");
      renderHealth();
    }
    await refreshControllerData();
  } catch (error) {
    state.nodesLoadError = error.message;
    renderNodesPage();
  }
}

async function refreshAuditEvents() {
  const limit = Number($("audit-limit")?.value || 200);
  const eventType = ($("audit-filter-type")?.value || "").trim();
  const target = ($("audit-filter-target")?.value || "").trim();
  const dryRun = ($("audit-filter-dry-run")?.value || "").trim();
  const fromRaw = ($("audit-filter-from")?.value || "").trim();
  const toRaw = ($("audit-filter-to")?.value || "").trim();
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (eventType) params.set("event_type", eventType);
  if (target) params.set("target", target);
  if (dryRun) params.set("dry_run", dryRun);
  if (fromRaw) params.set("created_from", new Date(fromRaw).toISOString());
  if (toRaw) params.set("created_to", new Date(toRaw).toISOString());
  try {
    state.auditEvents = await api(`/audit/events?${params.toString()}`);
  } catch (_error) {
    state.auditEvents = [];
  }
  renderAudit();
}

function renderAudit() {
  const body = $("audit-events-body");
  if (!body) return;
  const events = state.auditEvents;
  if (!events.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">No audit events.</td></tr>`;
    return;
  }
  body.innerHTML = events.map((event) => `<tr>
    <td>${escapeHtml(event.created_at || "-")}</td>
    <td>${escapeHtml(event.event_type || "-")}</td>
    <td>${escapeHtml(String(Boolean(event.dry_run)))}</td>
    <td>${escapeHtml(event.target || "-")}</td>
    <td>${escapeHtml(event.route || "-")}</td>
    <td><button type="button" data-audit-id="${escapeHtml(event.id)}">View</button></td>
  </tr>`).join("");
  body.querySelectorAll("[data-audit-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.getAttribute("data-audit-id");
      const event = state.auditEvents.find((item) => item.id === id);
      $("audit-event-detail").textContent = JSON.stringify(event || {}, null, 2);
    });
  });
}

function applyMyActionsFilter() {
  if (!state.authUser) return showToast("Login first.");
  const mine = state.auditEvents.filter((event) => String(event.actor || "") === state.authUser);
  const body = $("audit-events-body");
  if (!body) return;
  if (!mine.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">No audit events for current user.</td></tr>`;
    return;
  }
  body.innerHTML = mine.map((event) => `<tr>
    <td>${escapeHtml(event.created_at || "-")}</td>
    <td>${escapeHtml(event.event_type || "-")}</td>
    <td>${escapeHtml(String(Boolean(event.dry_run)))}</td>
    <td>${escapeHtml(event.target || "-")}</td>
    <td>${escapeHtml(event.route || "-")}</td>
    <td><button type="button" data-audit-id="${escapeHtml(event.id)}">View</button></td>
  </tr>`).join("");
}

async function refreshAuthKeys() {
  const body = $("keys-body");
  if (!body) return;
  if (state.authRole !== "admin") {
    state.authKeys = [];
    body.innerHTML = `<tr><td colspan="6" class="empty">Admin role required.</td></tr>`;
    return;
  }
  try {
    state.authKeys = await api("/auth/keys");
  } catch (_error) {
    state.authKeys = [];
  }
  renderAuthKeys();
}

function renderAuthKeys() {
  const body = $("keys-body");
  if (!body) return;
  if (!state.authKeys.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">No keys found.</td></tr>`;
    return;
  }
  body.innerHTML = state.authKeys.map((key) => `<tr>
    <td>${escapeHtml(key.username)}</td>
    <td>${escapeHtml(key.role)}</td>
    <td>${escapeHtml(key.key_hint || "-")}</td>
    <td>${escapeHtml(String(Boolean(key.revoked)))}</td>
    <td>${escapeHtml(key.created_at || "-")}</td>
    <td><button type="button" data-revoke-key="${escapeHtml(key.id)}" ${key.revoked ? "disabled" : ""}>Revoke</button></td>
  </tr>`).join("");
  body.querySelectorAll("[data-revoke-key]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const keyId = btn.getAttribute("data-revoke-key");
      if (!keyId) return;
      await api(`/auth/keys/${encodeURIComponent(keyId)}/revoke`, { method: "POST" });
      await writeAuditEvent({ actor: state.authUser || "unknown", event_type: "auth_key_revoke", dry_run: false, target: keyId, route: "auth", payload: {} });
      await refreshAuthKeys();
      showToast("Key revoked");
    });
  });
}

async function createAuthKey() {
  if (state.authRole !== "admin") return showToast("Admin role required.");
  const username = ($("keys-username").value || "").trim();
  const role = ($("keys-role").value || "operator").trim();
  if (!username) return showToast("Enter username for key.");
  const created = await api("/auth/keys", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, role }),
  });
  $("keys-create-output").textContent = JSON.stringify(created, null, 2);
  await writeAuditEvent({ actor: state.authUser || "unknown", event_type: "auth_key_create", dry_run: false, target: username, route: "auth", payload: { role, key_id: created.id } });
  await refreshAuthKeys();
}

async function refreshChatSessions() {
  try {
    state.chatSessions = await api("/chat/sessions");
  } catch (_error) {
    state.chatSessions = [];
  }
  renderChatSessionOptions();
}

function getStoredActiveChatSessionId() {
  try {
    return localStorage.getItem(ACTIVE_CHAT_SESSION_STORAGE_KEY) || "";
  } catch (_error) {
    return "";
  }
}

function persistActiveChatSessionId(sessionId) {
  try {
    if (sessionId) {
      localStorage.setItem(ACTIVE_CHAT_SESSION_STORAGE_KEY, sessionId);
    } else {
      localStorage.removeItem(ACTIVE_CHAT_SESSION_STORAGE_KEY);
    }
  } catch (_error) {
    // ignore storage failures
  }
}

function clearActiveChatSessionSelection() {
  state.selectedChatSessionId = "";
  persistActiveChatSessionId("");
  const select = $("chat-session-select");
  if (select) {
    select.value = "";
  }
}

function renderChatSessionOptions() {
  const select = $("chat-session-select");
  if (!select) return;
  if (!state.chatSessions.length) {
    clearActiveChatSessionSelection();
    select.innerHTML = `<option value="">No saved sessions</option>`;
    return;
  }
  select.innerHTML = state.chatSessions
    .map((session) => `<option value="${escapeHtml(session.id)}">${escapeHtml(session.name)} (${escapeHtml(session.model)})</option>`)
    .join("");
  const selectedId = chooseChatSessionToResume({
    sessions: state.chatSessions,
    preferredSessionId: state.selectedChatSessionId || getStoredActiveChatSessionId(),
  });
  if (!selectedId) {
    clearActiveChatSessionSelection();
    select.value = "";
    return;
  }
  state.selectedChatSessionId = selectedId;
  persistActiveChatSessionId(selectedId);
  select.value = selectedId;
}

async function resumeActiveChatSession() {
  if (!state.chatSessions.length) {
    return;
  }
  const sessionId = chooseChatSessionToResume({
    sessions: state.chatSessions,
    preferredSessionId: state.selectedChatSessionId || getStoredActiveChatSessionId(),
  });
  if (!sessionId) {
    clearActiveChatSessionSelection();
    return;
  }
  const currentSession = state.chatSessions.find((session) => session.id === sessionId);
  if (!isChatSessionReusable(currentSession)) {
    clearActiveChatSessionSelection();
    return;
  }
  if (state.selectedChatSessionId === sessionId && state.chatMessages.length) {
    persistActiveChatSessionId(sessionId);
    return;
  }
  const previousSelectedId = state.selectedChatSessionId;
  state.selectedChatSessionId = sessionId;
  $("chat-session-select").value = sessionId;
  if (previousSelectedId !== sessionId || !state.chatMessages.length) {
    await loadChatSession({ sessionId, silent: true });
  }
}



function filteredControllerJobs() {
  const status = ($("jobs-filter-status")?.value || "").trim().toLowerCase();
  const type = ($("jobs-filter-type")?.value || "").trim().toLowerCase();
  const target = ($("jobs-filter-target")?.value || "").trim().toLowerCase();
  return state.controllerJobs.filter((job) => {
    const okStatus = !status || String(job.status || "").toLowerCase().includes(status);
    const okType = !type || String(job.type || "").toLowerCase().includes(type);
    const okTarget = !target || String(job.target_selector || "auto").toLowerCase().includes(target);
    return okStatus && okType && okTarget;
  });
}

function renderControllerOps() {
  const jobsBody = $("controller-jobs-body");
  if (!jobsBody) return;
  if (state.health?.mode !== "controller") {
    jobsBody.innerHTML = `<tr><td colspan="6" class="empty">Controller mode only.</td></tr>`;
    $("controller-node-capabilities").innerHTML = "Controller mode only.";
    $("controller-retention").innerHTML = "Controller mode only.";
    return;
  }
  const jobs = filteredControllerJobs();
  if (!jobs.length) {
    jobsBody.innerHTML = `<tr><td colspan="6" class="empty">No jobs found.</td></tr>`;
  } else {
    jobsBody.innerHTML = jobs.map((job) => `<tr>
      <td class="path" title="${escapeHtml(job.id)}">${escapeHtml(job.id.slice(0, 8))}</td>
      <td>${escapeHtml(job.status)}</td>
      <td>${escapeHtml(job.type)}</td>
      <td>${escapeHtml(job.target_selector || "auto")}</td>
      <td>${escapeHtml(job.updated_at || "-")}</td>
      <td><button type="button" data-job-detail="${escapeHtml(job.id)}">View</button></td>
    </tr>`).join("");
  }
  jobsBody.querySelectorAll("[data-job-detail]").forEach((button) => {
    button.addEventListener("click", async () => {
      const jobId = button.getAttribute("data-job-detail");
      const [job, events, artifacts] = await Promise.all([
        api(`/jobs/${encodeURIComponent(jobId)}`),
        api(`/jobs/${encodeURIComponent(jobId)}/events?limit=200`),
        api(`/jobs/${encodeURIComponent(jobId)}/artifacts`),
      ]);
      $("controller-job-detail").innerHTML = renderControllerJobDetail(job, events, artifacts);
    });
  });

  const nodeSummary = state.nodeModels.map((node) => ({
    name: node.name,
    reachable: node.reachable,
    models: (node.models || []).length,
    heartbeat: node.last_heartbeat,
    source: node.models_source,
  }));
  $("controller-node-capabilities").innerHTML = renderNodeCapabilityTable(nodeSummary);
  $("controller-retention").innerHTML = renderRetentionPanel(state.retentionPolicy, state.controllerStats);
}

function renderControllerJobDetail(job, events, artifacts) {
  const summary = `<div><strong>${escapeHtml(job.id)}</strong></div>
    <div class="muted">status=${escapeHtml(job.status)} type=${escapeHtml(job.type)} target=${escapeHtml(job.target_selector || "auto")}</div>
    <div class="muted">created=${escapeHtml(job.created_at || "-")} updated=${escapeHtml(job.updated_at || "-")}</div>`;
  const eventRows = (events || []).map((event) => `<tr class="${eventRowClass(event.event_type || "")}">
    <td>${escapeHtml(event.created_at || "-")}</td>
    <td>${escapeHtml(event.event_type || "-")}</td>
    <td class="path" title="${escapeHtml(JSON.stringify(event.event_json || {}))}">${escapeHtml(JSON.stringify(event.event_json || {}))}</td>
  </tr>`).join("");
  const artifactRows = (artifacts || []).map((artifact) => `<tr>
    <td>${escapeHtml(artifact.kind || "-")}</td>
    <td class="path" title="${escapeHtml(artifact.uri || "-")}">${escapeHtml(artifact.uri || "-")}</td>
    <td class="path" title="${escapeHtml(JSON.stringify(artifact.meta || {}))}">${escapeHtml(JSON.stringify(artifact.meta || {}))}</td>
  </tr>`).join("");
  return `${summary}
    <h4>Events</h4>
    <div class="table-wrap"><table><thead><tr><th>Time</th><th>Type</th><th>Payload</th></tr></thead><tbody>${eventRows || '<tr><td colspan="3" class="empty">No events.</td></tr>'}</tbody></table></div>
    <h4>Artifacts</h4>
    <div class="table-wrap"><table><thead><tr><th>Kind</th><th>URI</th><th>Meta</th></tr></thead><tbody>${artifactRows || '<tr><td colspan="3" class="empty">No artifacts.</td></tr>'}</tbody></table></div>`;
}

function renderNodeCapabilityTable(nodes) {
  const rows = (nodes || []).map((node) => `<tr>
    <td>${escapeHtml(node.name)}</td>
    <td>${escapeHtml(String(node.reachable))}</td>
    <td>${escapeHtml(String(node.models))}</td>
    <td>${escapeHtml(node.source || "-")}</td>
    <td>${escapeHtml(node.heartbeat || "-")}</td>
  </tr>`).join("");
  return `<div class="table-wrap"><table>
    <thead><tr><th>Node</th><th>Reachable</th><th>Models</th><th>Source</th><th>Heartbeat</th></tr></thead>
    <tbody>${rows || '<tr><td colspan="5" class="empty">No nodes.</td></tr>'}</tbody>
  </table></div>`;
}

function renderRetentionPanel(policy, stats) {
  return `<div><strong>Policy</strong></div>
    <div class="muted">retention_days=${escapeHtml(String(policy?.retention_days ?? "-"))}</div>
    <div class="muted">archive_retention_days=${escapeHtml(String(policy?.archive_retention_days ?? "-"))}</div>
    <h4>Last Sweep</h4>
    <div class="muted">${escapeHtml(JSON.stringify(stats?.last_sweep || {}, null, 2))}</div>
    <h4>Job Counts</h4>
    <div class="muted">${escapeHtml(JSON.stringify(stats?.job_counts || {}, null, 2))}</div>`;
}

function setActivePage(page) {
  const nextPage = document.querySelector(`[data-page="${page}"]`) ? page : "dashboard";
  state.activePage = nextPage;

  document.querySelectorAll("[data-page]").forEach((pageElement) => {
    pageElement.classList.toggle("active", pageElement.dataset.page === nextPage);
  });
  document.querySelectorAll("[data-page-target]").forEach((button) => {
    const active = button.dataset.pageTarget === nextPage;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });

  if (window.location.hash !== `#${nextPage}`) {
    window.history.replaceState(null, "", `#${nextPage}`);
  }

  renderActivePage();
}

function renderActivePage() {
  if (state.activePage === "nodes") {
    renderNodesPage();
    void refreshNodesPageData();
  }
  if (state.activePage === "chat") {
    renderChatModelOptions();
    void refreshChatCapabilities();
    void resumeActiveChatSession();
  }
  if (state.activePage === "embeddings") {
    renderEmbeddingsModelOptions();
    void refreshKvCapabilities();
  }
  if (state.activePage === "dashboard") {
    if (state.health) renderHealth();
    renderLocalModels();
    renderNodes();
  }
  if (state.activePage === "controller-ops") renderControllerOps();
  if (state.activePage === "audit") renderAudit();
  if (state.activePage === "gguf-library") renderGgufLibrary();
  if (state.activePage === "hf-to-gguf") renderConversions();
  if (state.activePage === "hf-downloads") renderDownloads();
  if (state.activePage === "quantization") renderQuantizations();
  if (state.activePage === "settings") renderSettingsConfig();
}

function renderSettingsConfig() {
  const mode = $("settings-mode")?.value || "single";
  const logDir = ($("settings-log-dir")?.value || "./logs").trim() || "./logs";
  const controllerUrl = ($("settings-controller-url")?.value || "http://127.0.0.1:9137").trim();
  const controllerApiKey = ($("settings-controller-api-key")?.value || "").trim();
  const registrationKey = ($("settings-registration-key")?.value || "").trim();
  const agentApiKey = ($("settings-agent-api-key")?.value || "").trim();
  const agentName = ($("settings-agent-name")?.value || "local-agent").trim() || "local-agent";
  const agentUrl = ($("settings-agent-url")?.value || "http://127.0.0.1:9000").trim() || "http://127.0.0.1:9000";

  const lines = [`mode: ${mode}`, `log_dir: ${JSON.stringify(logDir)}`, "models: {}"];
  if (mode === "controller") {
    lines.push("nodes:");
    lines.push(`  ${agentName}:`);
    lines.push(`    url: ${JSON.stringify(agentUrl)}`);
    lines.push(`    api_key: ${JSON.stringify(agentApiKey || "CHANGE_ME_AGENT_API_KEY")}`);
    lines.push("    verify_tls: true");
  }
  if (mode === "agent") {
    lines.push(`controller_url: ${JSON.stringify(controllerUrl)}`);
    lines.push(`controller_registration_key_outbound: ${JSON.stringify(registrationKey || "CHANGE_ME_REGISTRATION_KEY")}`);
    if (controllerApiKey) lines.push(`controller_api_key: ${JSON.stringify(controllerApiKey)}`);
  }
  if (mode === "single" && controllerApiKey) {
    lines.push(`api_key: ${JSON.stringify(controllerApiKey)}`);
  }
  $("settings-config-output").textContent = `${lines.join("\n")}\n`;

  const exports = [`export LLAMA_MANAGER_CONFIG=config.yaml`, `export LLAMA_MANAGER_MODE=${mode}`];
  if (mode === "agent") {
    exports.push(`export LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND=${shellQuote(registrationKey || "CHANGE_ME_REGISTRATION_KEY")}`);
    exports.push(`export LLAMA_MANAGER_CONTROLLER_URL=${shellQuote(controllerUrl || "http://127.0.0.1:9137")}`);
    if (controllerApiKey) exports.push(`export LLAMA_MANAGER_CONTROLLER_API_KEY=${shellQuote(controllerApiKey)}`);
  } else if (mode === "controller") {
    exports.push(`export LLAMA_MANAGER_AGENT_API_KEY=${shellQuote(agentApiKey || "CHANGE_ME_AGENT_API_KEY")}`);
  } else if (controllerApiKey) {
    exports.push(`export LLAMA_MANAGER_API_KEY=${shellQuote(controllerApiKey)}`);
  }
  $("settings-exports-output").textContent = `${exports.join("\n")}\n`;
}

async function generateSettingsApiKeys() {
  const prefix = ($("settings-key-prefix")?.value || "llm").trim();
  const tokenBytes = Number($("settings-key-bytes")?.value || 32);
  const count = Number($("settings-key-count")?.value || 1);
  const payload = await api("/settings/api-keys/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ prefix, token_bytes: tokenBytes, count }),
  });
  $("settings-generated-keys-output").textContent = JSON.stringify(payload, null, 2);
  return payload;
}

function shellQuote(value) {
  const text = String(value ?? "");
  return `'${text.replaceAll("'", "'\"'\"'")}'`;
}

function renderGgufLibrary() {
  const body = $("library-body");
  if (!state.ggufFiles.length) {
    body.innerHTML = `<p class="empty">No GGUF files found under HF models.</p>`;
    return;
  }
  const added = state.ggufFiles.filter((file) => Boolean(file.registered));
  const available = state.ggufFiles.filter((file) => !file.registered);
  body.innerHTML = [
    `<section class="library-section">
      <header class="library-section-header">
        <h3>Added Models</h3>
        <p>Models already configured in your local config and available for use.</p>
      </header>
      <div class="library-cards">
        ${added.length ? added.map((file) => libraryCard(file)).join("") : `<p class="empty">No added models yet.</p>`}
      </div>
    </section>`,
    `<section class="library-section">
      <header class="library-section-header">
        <h3>Available GGUF Files</h3>
        <p>Discovered files not yet added to your local config.</p>
      </header>
      <div class="library-cards">
        ${available.length ? available.map((file) => libraryCard(file)).join("") : `<p class="empty">All discovered files are already added.</p>`}
      </div>
    </section>`,
  ].join("");
  bindLibraryCards(body);
}

function renderConversions() {
  const body = $("conversions-body");
  if (!state.conversions.length) {
    body.innerHTML = `<tr><td colspan="7" class="empty">No convertible HF models found.</td></tr>`;
    return;
  }

  body.innerHTML = state.conversions.map((model) => conversionRow(model)).join("");
  bindConversionButtons(body);
}

function renderQuantizations() {
  const body = $("quantizations-body");
  if (!state.quantizations.length) {
    body.innerHTML = `<tr><td colspan="7" class="empty">No GGUF files found for quantization.</td></tr>`;
    return;
  }

  body.innerHTML = state.quantizations.map((file) => quantizationRow(file)).join("");
  bindQuantizationButtons(body);
}

function renderDownloads() {
  const body = $("downloads-body");
  if (!body) return;
  if (!state.downloads.length) {
    body.innerHTML = `<tr><td colspan="7" class="empty">No download history yet.</td></tr>`;
    return;
  }
  body.innerHTML = state.downloads.map((item) => `<tr>
    <td><strong>${escapeHtml(item.repo_id)}</strong></td>
    <td><span class="status ${item.status === "running" ? "running" : item.status === "succeeded" ? "stopped" : "error"}">${escapeHtml(item.status)}</span></td>
    <td>${escapeHtml(item.started_at || "-")}</td>
    <td>${escapeHtml(item.finished_at || "-")}</td>
    <td class="path" title="${escapeHtml(item.local_path || "-")}">${escapeHtml(item.local_path || "-")}</td>
    <td>${escapeHtml(item.triggered_by || "-")}</td>
    <td><div class="actions" data-download-id="${escapeHtml(item.id)}" data-download-repo="${escapeHtml(item.repo_id)}"><button class="primary" data-download-action="start" ${item.status === "running" ? "disabled" : ""}>Download</button><button data-download-action="logs">Logs</button><button data-download-action="delete" ${item.status === "running" ? "disabled" : ""}>Delete</button></div></td>
  </tr>`).join("");
  body.querySelectorAll("button[data-download-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const container = button.closest(".actions");
      await runDownloadAction({
        downloadId: container.dataset.downloadId,
        repoId: container.dataset.downloadRepo,
        action: button.dataset.downloadAction,
      });
    });
  });
}

async function runDownloadAction({ downloadId, repoId, action }) {
  try {
    if (action === "logs") {
      const payload = await api(`/downloads/${encodeURIComponent(downloadId)}/logs?lines=200`);
      $("log-title").textContent = `download / ${repoId}`;
      $("log-output").textContent = payload.text || "No download log output.";
      openLogModal();
      return;
    }
    if (action === "delete") {
      if (!confirmAction(`Delete download history item for ${repoId}?`)) return;
      await api(`/downloads/${encodeURIComponent(downloadId)}`, { method: "DELETE" });
      showToast(`deleted download record for ${repoId}`);
      await refreshAll();
      return;
    }
    const revision = ($("download-revision")?.value || "").trim();
    await api(`/downloads/${encodeURIComponent(repoId)}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ revision: revision || null }),
    });
    showToast(`download started for ${repoId}`);
    await refreshAll();
  } catch (error) {
    showToast(error.message);
  }
}

function renderHealth() {
  const health = state.health;
  $("subtitle").textContent = health.ok
    ? "FastAPI service is reachable"
    : "FastAPI service reported an issue";
  $("mode-pill").textContent = health.mode;
  $("cpu-value").textContent = formatCpu(health.system?.cpu);
  $("ram-value").textContent = formatRam(health.system?.ram);
  $("vram-value").textContent = formatVram(health.system?.vram);
  $("configured-value").textContent =
    health.mode === "controller"
      ? `${health.nodes_configured} nodes`
      : `${health.models_configured} models`;
}

function renderLocalModels() {
  const body = $("models-body");
  if (!state.localModels.length) {
    body.innerHTML = `<p class="empty">No local models configured.</p>`;
    return;
  }

  body.innerHTML = sortModelsForDisplay(state.localModels).map((model) => modelCard(model)).join("");
  bindModelButtons(body);
  bindFavoriteButtons(body);
}

function renderChatModelOptions() {
  const select = $("chat-model");
  const selected = select.value;
  const modelsByName = new Map();
  for (const model of state.localModels) {
    modelsByName.set(model.name, model);
  }
  for (const node of state.nodeModels) {
    for (const model of node.models || []) {
      if (!modelsByName.has(model.name)) {
        modelsByName.set(model.name, model);
      }
    }
  }
  const availableModels = Array.from(modelsByName.values());
  if (!availableModels.length) {
    select.innerHTML = `<option value="">No configured models</option>`;
    $("send-chat-button").disabled = true;
    $("chat-state").textContent = "No configured models";
    return;
  }

  select.innerHTML = availableModels
    .map((model) => `<option value="${escapeHtml(model.name)}">${escapeHtml(model.name)} :${model.port}</option>`)
    .join("");
  if (availableModels.some((model) => model.name === selected)) {
    select.value = selected;
  }
  renderChatTargetOptions();
  renderEmbeddingsModelOptions();
  if (state.activePage === "chat") {
    void refreshChatCapabilities();
  } else if (state.activePage === "embeddings") {
    void refreshKvCapabilities();
  }
  $("send-chat-button").disabled = state.chatPending;
  $("chat-state").textContent = state.chatPending ? "Waiting for response..." : "Ready";
}

function renderEmbeddingsModelOptions() {
  const model = $("chat-model")?.value || "";
  if ($("embeddings-model")) $("embeddings-model").innerHTML = $("chat-model").innerHTML;
  if ($("embeddings-target")) $("embeddings-target").innerHTML = $("chat-target").innerHTML;
  if ($("embeddings-model") && model) $("embeddings-model").value = model;
}

async function refreshChatCapabilities() {
  const model = $("chat-model").value;
  if (!model) {
    state.chatCapabilities = null;
    renderChatCapabilitiesDetail();
    return;
  }
  try {
    state.chatCapabilities = await api(`/chat/capabilities/${encodeURIComponent(model)}`);
  } catch (_error) {
    state.chatCapabilities = null;
  }
  applyCapabilityGates();
  renderChatCapabilitiesDetail();
  await refreshKvCapabilities();
}

function applyCapabilityGates() {
  const sampling = state.chatCapabilities?.supports?.sampling || {};
  const gates = [
    ["chat-top-p", sampling.top_p],
    ["chat-top-k", sampling.top_k],
    ["chat-min-p", sampling.min_p],
    ["chat-repeat-penalty", sampling.repeat_penalty],
    ["chat-seed", sampling.seed],
    ["chat-stop", sampling.stop],
  ];
  for (const [id, enabled] of gates) {
    const el = $(id);
    el.disabled = enabled === false;
  }
  const clearBtn = $("chat-kv-clear-button");
  if (clearBtn) clearBtn.disabled = state.kvCapabilities?.supports?.clear_slot === false;
  applyStructuredCapabilityGates();
  renderFeatureMatrix();
}

function applyStructuredCapabilityGates() {
  const select = $("chat-structured-mode");
  if (!select) return;
  const structured = state.chatCapabilities?.supports?.structured_output || {};
  const schemaSupported = structured.json_schema !== false;
  const grammarSupported = structured.grammar !== false;
  [...select.options].forEach((option) => {
    if (option.value === "json_schema") option.disabled = !schemaSupported;
    if (option.value === "grammar") option.disabled = !grammarSupported;
  });
  if ((select.value === "json_schema" && !schemaSupported) || (select.value === "grammar" && !grammarSupported)) {
    select.value = "none";
  }
  applyStructuredModeUI();
}

function renderFeatureMatrix() {
  const el = $("chat-feature-matrix");
  if (!el) return;
  const s = state.chatCapabilities?.supports || {};
  const kv = state.kvCapabilities?.supports || {};
  const structuredSource = s.structured_output_source || {};
  const yes = (v) => (v ? "supported" : "unsupported");
  el.textContent = [
    `chat: ${yes(Boolean(s.stream))}`,
    `embeddings: ${yes(true)}`,
    `slots(list): ${yes(kv.list_slots)}`,
    `slots(clear): ${yes(kv.clear_slot)}`,
    `structured(json_schema): ${yes(s.structured_output?.json_schema)} [${structuredSource.json_schema || "default"}]`,
    `structured(grammar): ${yes(s.structured_output?.grammar)} [${structuredSource.grammar || "default"}]`,
    `multimodal(vision): ${yes(s.vision)}`,
  ].join(" | ");
}

function renderChatCapabilitiesDetail() {
  const el = $("chat-capabilities-detail");
  if (!el) return;
  if (!state.chatCapabilities) {
    el.textContent = "Capabilities detail unavailable";
    return;
  }
  el.textContent = JSON.stringify(state.chatCapabilities, null, 2);
}

async function copyChatCapabilitiesJson() {
  if (!state.chatCapabilities) {
    showToast("No capabilities to copy.");
    return;
  }
  try {
    await navigator.clipboard.writeText(JSON.stringify(state.chatCapabilities, null, 2));
    showToast("Capabilities JSON copied");
  } catch (_error) {
    showToast("Clipboard copy failed");
  }
}

function shouldDryRun() {
  return Boolean($("dry-run-toggle")?.checked);
}

function confirmAction(message) {
  return window.confirm(message);
}

async function writeAuditEvent(event) {
  try {
    await api("/audit/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
    });
  } catch (_error) {
    // Non-blocking for UX; action should still proceed.
  }
}

async function refreshKvCapabilities() {
  const model = $("chat-model").value;
  const target = $("chat-target").value || "auto";
  if (!model) {
    state.kvCapabilities = null;
    return;
  }
  try {
    state.kvCapabilities = await api(
      `/chat/${encodeURIComponent(model)}/kv/capabilities?target=${encodeURIComponent(target)}`
    );
  } catch (_error) {
    state.kvCapabilities = null;
  }
  const clearBtn = $("chat-kv-clear-button");
  if (clearBtn) clearBtn.disabled = state.kvCapabilities?.supports?.clear_slot !== true;
}

function renderChatTargetOptions() {
  const select = $("chat-target");
  const selected = select.value || "auto";
  const nodeOptions = state.nodeModels.map((node) => {
    const label = node.reachable ? `Node: ${node.name}` : `Node: ${node.name} (offline)`;
    return `<option value="node:${escapeHtml(node.name)}">${escapeHtml(label)}</option>`;
  });
  select.innerHTML = [
    `<option value="auto">Auto (local first, then nodes)</option>`,
    `<option value="local">Local only</option>`,
    ...nodeOptions,
  ].join("");
  if ([...select.options].some((option) => option.value === selected)) {
    select.value = selected;
  } else {
    select.value = "auto";
  }
}

function libraryCard(file) {
  const status = file.registered ? `added as ${file.registered_as}` : "available";
  const statusClass = file.registered ? "running" : "stopped";
  return `<article class="library-card" tabindex="0" data-gguf-card="${escapeHtml(file.id)}" aria-label="Open details for ${escapeHtml(file.filename)}">
    <h3>${escapeHtml(file.filename)}</h3>
    <div class="library-card-grid">
      <div class="k">Directory</div><div class="v">${escapeHtml(file.model_dir)}</div>
      <div class="k">Library Name</div><div class="v">${escapeHtml(file.name || "-")}</div>
      <div class="k">Size</div><div class="v">${escapeHtml(formatGb(file.size_gb))} (${escapeHtml(formatBytes(file.size_bytes))})</div>
      <div class="k">Status</div><div class="v"><span class="status ${statusClass}">${escapeHtml(status)}</span></div>
      <div class="k">Path</div><div class="v mono" title="${escapeHtml(file.path)}">${escapeHtml(file.path)}</div>
      <div class="k">File ID</div><div class="v mono">${escapeHtml(file.id)}</div>
    </div>
  </article>`;
}

function bindLibraryCards(root) {
  root.querySelectorAll("[data-gguf-card]").forEach((card) => {
    const open = () => openGgufDetail(card.dataset.ggufCard);
    card.addEventListener("click", open);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
}

function openGgufDetail(fileId) {
  const file = state.ggufFiles.find((item) => item.id === fileId);
  if (!file) {
    showToast("GGUF file is no longer available.");
    return;
  }
  state.selectedGgufId = fileId;
  $("library-model-name").value = suggestedGgufModelName(file);
  $("gguf-detail-title").textContent = file.filename;
  $("gguf-detail-body").innerHTML = ggufDetailMarkup(file);
  $("gguf-detail-add-button").disabled = Boolean(file.registered);
  $("gguf-detail-add-button").textContent = file.registered ? "Already Added" : "Add Model";
  const removeBtn = $("gguf-detail-remove-button");
  if (removeBtn) {
    removeBtn.disabled = !file.registered_as;
    removeBtn.textContent = file.registered_as ? `Remove ${file.registered_as}` : "Remove Model";
  }
  openModal("gguf-detail-modal");
}

function ggufDetailMarkup(file) {
  const fields = [
    ["Directory", file.model_dir],
    ["File", file.filename],
    ["Library name", file.name],
    ["Size", `${formatGb(file.size_gb)} (${formatBytes(file.size_bytes)})`],
    ["Status", file.registered ? `Added as ${file.registered_as}` : "Available"],
    ["Path", file.path, true],
    ["File ID", file.id, true],
  ];
  return fields.map(([label, value, mono]) => `<div><span class="detail-label">${escapeHtml(label)}</span><span class="detail-value ${mono ? "mono" : ""}">${escapeHtml(value ?? "-")}</span></div>`).join("");
}

function renderNodes() {
  const panel = $("nodes-panel");
  const body = $("nodes-body");
  if (state.health?.mode !== "controller") {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;

  if (!state.nodeModels.length) {
    body.innerHTML = `<p class="empty">No nodes configured.</p>`;
    return;
  }

  body.innerHTML = state.nodeModels
    .map((node) => nodeCard(node, { compact: true }))
    .join("");

  bindModelButtons(body);
}

function filteredNodes() {
  const query = ($("nodes-filter-name")?.value || "").trim();
  const status = ($("nodes-filter-status")?.value || "").trim();
  const registration = ($("nodes-filter-registration")?.value || "").trim();
  return filterNodes(state.nodeModels, { query, status, registration });
}

function renderNodesPage() {
  const body = $("nodes-page-body");
  const summary = $("nodes-page-summary");
  if (!body) return;
  if (state.health?.mode !== "controller") {
    body.innerHTML = `<p class="empty">Controller mode only.</p>`;
    if (summary) summary.textContent = "Controller node inventory";
    return;
  }

  const nodes = filteredNodes();
  const summaryData = nodeSummary(state.nodeModels);
  if (summary) {
    summary.textContent = `${summaryData.reachable}/${summaryData.total} reachable nodes, ${summaryData.models} reported models`;
  }

  if (state.nodesLoadError && !state.nodeModels.length) {
    body.innerHTML = `<p class="empty">Unable to load nodes: ${escapeHtml(state.nodesLoadError)}</p>`;
    return;
  }

  if (!nodes.length) {
    body.innerHTML = `<p class="empty">No nodes match the current filters.</p>`;
    return;
  }

  body.innerHTML = nodes.map((node) => nodeCard(node, { compact: false })).join("");
  bindModelButtons(body);
  bindNodeEditButtons(body);
}

function nodeCard(node, { compact }) {
  const models = node.models?.length
    ? `<div class="model-cards">${sortModelsForDisplay(node.models).map((model) => modelCard(model, node.name)).join("")}</div>`
    : `<p class="empty">${escapeHtml(node.error || "No models reported.")}</p>`;
  const heartbeat = node.heartbeat_age_seconds == null ? "-" : `${node.heartbeat_age_seconds}s`;
  const provenance = [
    `Controller config: ${node.controller_config_source || "-"}`,
    `Agent config: ${node.agent_config_source || "-"}`,
    `Model source: ${node.models_source || "unknown"}`,
    `Last heartbeat: ${node.last_heartbeat || "-"}`,
  ].join("\n");
  const meta = compact
    ? `<div class="node-url" title="${escapeHtml(provenance)}">${escapeHtml(
        `cfg: ${node.agent_config_source || "-"} | models: ${node.models_source || "unknown"}`
      )}</div>`
    : `<div class="node-meta-grid">
        <div><span class="label">Registration</span><strong>${escapeHtml(node.registration || "-")}</strong></div>
        <div><span class="label">Heartbeat</span><strong>${escapeHtml(node.heartbeat_fresh === false ? "stale" : "fresh")}</strong><small>${escapeHtml(heartbeat)}</small></div>
        <div><span class="label">Agent config</span><strong title="${escapeHtml(node.agent_config_source || "-")}">${escapeHtml(shortPath(node.agent_config_source || "-"))}</strong></div>
        <div><span class="label">Model source</span><strong>${escapeHtml(node.models_source || "unknown")}</strong></div>
      </div>`;

  return `<article class="node ${compact ? "node-compact" : "node-full"}">
    <div class="node-header">
      <div>
        <strong>${escapeHtml(node.name)}</strong>
        <div class="node-url">${escapeHtml(node.url)}</div>
        ${meta}
      </div>
      <div class="node-header-actions">
        <span class="status ${node.reachable ? "reachable" : "error"}">
          ${node.reachable ? "reachable" : "offline"}
        </span>
        ${nodeEditMarkup(node, { compact })}
      </div>
    </div>
    ${models}
  </article>`;
}

function bindNodeEditButtons(root) {
  root.querySelectorAll("button[data-edit-node]").forEach((button) => {
    button.addEventListener("click", () => openNodeEditModal(button.dataset.editNode || ""));
  });
}

function openNodeEditModal(nodeName) {
  const node = state.nodeModels.find((item) => item.name === nodeName);
  if (!node) {
    showToast("Node is no longer available.");
    return;
  }
  const defaults = nodeEditFormDefaults(node);
  $("node-edit-name").value = defaults.name;
  $("node-edit-url").value = defaults.url;
  $("node-edit-api-key").value = defaults.api_key;
  $("node-edit-verify-tls").checked = defaults.verify_tls;
  $("node-edit-title").textContent = `Edit ${defaults.name}`;
  openModal("node-edit-modal");
}

async function saveNodeEdit() {
  const name = ($("node-edit-name")?.value || "").trim();
  const url = ($("node-edit-url")?.value || "").trim();
  const apiKey = $("node-edit-api-key")?.value || "";
  const verifyTls = Boolean($("node-edit-verify-tls")?.checked);
  if (!name || !url) return showToast("Enter a node URL.");
  await api(`/nodes/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ url, api_key: apiKey.trim() || null, verify_tls: verifyTls }),
  });
  closeModal($("node-edit-modal"));
  await refreshNodesPageData();
  showToast(`Updated ${name}`);
}

function modelRow(model, nodeName = null) {
  const running = Boolean(model.running);
  const scope = nodeName ? `data-node="${escapeHtml(nodeName)}"` : "";
  const favoriteButton = nodeName
    ? ""
    : `<button class="icon-button favorite-button ${model.favorite ? "active" : ""}" type="button" data-favorite-model="${escapeHtml(model.name)}" data-favorite="${model.favorite ? "true" : "false"}" title="${model.favorite ? "Unfavorite model" : "Favorite model"}" aria-label="${model.favorite ? "Unfavorite model" : "Favorite model"}">${model.favorite ? "★" : "☆"}</button>`;
  return `<tr>
    <td><div class="model-name-cell">${favoriteButton}<strong>${escapeHtml(model.name)}</strong></div></td>
    <td><span class="status ${running ? "running" : "stopped"}">${running ? "running" : "stopped"}</span></td>
    <td>${model.port ?? "-"}</td>
    <td>${model.pid ?? "-"}</td>
    <td class="path" title="${escapeHtml(model.model_path || "")}">${escapeHtml(model.model_path || "-")}</td>
    <td>${escapeHtml(model.model_source || "unknown")}</td>
    <td>
      <div class="actions" ${scope} data-model="${escapeHtml(model.name)}">
        <button class="primary" data-action="start" ${running ? "disabled" : ""}>Start</button>
        <button class="danger" data-action="stop" ${running ? "" : "disabled"}>Stop</button>
        <button data-action="restart">Restart</button>
        <button data-action="logs">Logs</button>
      </div>
    </td>
  </tr>`;
}

function modelCard(model, nodeName = null) {
  const running = Boolean(model.running);
  const scope = nodeName ? `data-node="${escapeHtml(nodeName)}"` : "";
  const favoriteButton = nodeName
    ? ""
    : `<button class="icon-button favorite-button ${model.favorite ? "active" : ""}" type="button" data-favorite-model="${escapeHtml(model.name)}" data-favorite="${model.favorite ? "true" : "false"}" title="${model.favorite ? "Unfavorite model" : "Favorite model"}" aria-label="${model.favorite ? "Unfavorite model" : "Favorite model"}">${model.favorite ? "★" : "☆"}</button>`;
  return `<article class="model-card">
    <div class="model-card-head">
      <div class="model-name-cell">${favoriteButton}<strong>${escapeHtml(model.name)}</strong></div>
      <span class="status ${running ? "running" : "stopped"}">${running ? "running" : "stopped"}</span>
    </div>
    <div class="model-card-grid">
      <div><span class="label">Port</span><strong>${model.port ?? "-"}</strong></div>
      <div><span class="label">PID</span><strong>${model.pid ?? "-"}</strong></div>
      <div><span class="label">Source</span><strong>${escapeHtml(model.model_source || "unknown")}</strong></div>
      <div class="model-card-path"><span class="label">Path</span><strong title="${escapeHtml(model.model_path || "")}">${escapeHtml(model.model_path || "-")}</strong></div>
    </div>
    <div class="actions model-card-actions" ${scope} data-model="${escapeHtml(model.name)}">
      <button class="primary" data-action="start" ${running ? "disabled" : ""}>Start</button>
      <button class="danger" data-action="stop" ${running ? "" : "disabled"}>Stop</button>
      <button data-action="restart">Restart</button>
      <button data-action="logs">Logs</button>
    </div>
  </article>`;
}

function bindFavoriteButtons(root) {
  root.querySelectorAll("button[data-favorite-model]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const model = button.dataset.favoriteModel;
      const favorite = button.dataset.favorite !== "true";
      try {
        await api(`/models/${encodeURIComponent(model)}/favorite`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ favorite }),
        });
        showToast(`${favorite ? "favorited" : "unfavorited"} ${model}`);
        await refreshAll();
      } catch (error) {
        showToast(error.message);
      }
    });
  });
}

function bindModelButtons(root) {
  root.querySelectorAll("button[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const container = button.closest(".actions");
      const model = container.dataset.model;
      const node = container.dataset.node;
      const action = button.dataset.action;
      await runModelAction({ model, node, action });
    });
  });
}

function conversionRow(model) {
  const running = Boolean(model.running);
  const canConvert = Boolean(model.convertible) && !running;
  const statusClass = running ? "running" : model.convertible ? "stopped" : "error";
  const statusText = running
    ? `running pid ${model.pid}`
    : model.convertible
      ? "ready"
      : "not convertible";
  const ggufFiles = Array.isArray(model.gguf_files) ? model.gguf_files : [];
  const ggufLabel = ggufFiles.length ? `${ggufFiles.length} file${ggufFiles.length === 1 ? "" : "s"}` : "missing";
  const ggufTitle = ggufFiles.length ? ggufFiles.join("\n") : "No GGUF files found";
  return `<tr>
    <td><strong>${escapeHtml(model.name)}</strong></td>
    <td><span class="status ${statusClass}">${escapeHtml(statusText)}</span></td>
    <td title="${escapeHtml(ggufTitle)}">${escapeHtml(ggufLabel)}</td>
    <td class="path" title="${escapeHtml(model.path)}">${escapeHtml(model.path)}</td>
    <td class="path" title="${escapeHtml(model.output_path)}">${escapeHtml(model.output_path)}</td>
    <td class="path" title="${escapeHtml(model.python_bin || "")}">${escapeHtml(shortPath(model.python_bin || "-"))}</td>
    <td>
      <div class="actions" data-conversion="${escapeHtml(model.name)}">
        <button class="primary" data-conversion-action="start" ${canConvert ? "" : "disabled"}>Convert</button>
        <button data-conversion-action="logs">Logs</button>
      </div>
    </td>
  </tr>`;
}

function bindConversionButtons(root) {
  root.querySelectorAll("button[data-conversion-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const container = button.closest(".actions");
      await runConversionAction({
        model: container.dataset.conversion,
        action: button.dataset.conversionAction,
      });
    });
  });
}

function quantizationRow(file) {
  const running = Boolean(file.running);
  const ready = Boolean(file.quantize_bin) && !running;
  const statusClass = running ? "running" : file.quantize_bin ? "stopped" : "error";
  const statusText = running
    ? `running pid ${file.pid}`
    : file.quantize_bin
      ? "ready"
      : "missing binary";
  const supportedTypes = Array.isArray(file.supported_types) && file.supported_types.length
    ? file.supported_types
    : ["Q4_K_M"];
  const typeOptions = supportedTypes
    .map((type) => `<option value="${escapeHtml(type)}" ${type === file.type ? "selected" : ""}>${escapeHtml(type)}</option>`)
    .join("");
  const existingOutputs = Array.isArray(file.existing_outputs) ? file.existing_outputs : [];
  const outputTitle = [file.output_path, ...existingOutputs].filter(Boolean).join("\n");
  return `<tr>
    <td><strong>${escapeHtml(file.model_dir)}</strong></td>
    <td class="path" title="${escapeHtml(file.path)}">${escapeHtml(file.filename)}</td>
    <td>${escapeHtml(formatGb(file.size_gb))}</td>
    <td>
      <select class="compact-select" data-quantization-type>
        ${typeOptions}
      </select>
    </td>
    <td><span class="status ${statusClass}">${escapeHtml(statusText)}</span></td>
    <td class="path" title="${escapeHtml(outputTitle)}">${escapeHtml(shortPath(file.output_path || "-"))}</td>
    <td>
      <div class="actions" data-quantization="${escapeHtml(file.id)}" data-quantization-name="${escapeHtml(file.filename)}">
        <button class="primary" data-quantization-action="start" ${ready ? "" : "disabled"}>Quantize</button>
        <button data-quantization-action="logs">Logs</button>
      </div>
    </td>
  </tr>`;
}

function bindQuantizationButtons(root) {
  root.querySelectorAll("button[data-quantization-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const container = button.closest(".actions");
      const row = button.closest("tr");
      const type = row.querySelector("[data-quantization-type]")?.value || "Q4_K_M";
      await runQuantizationAction({
        fileId: container.dataset.quantization,
        filename: container.dataset.quantizationName,
        type,
        action: button.dataset.quantizationAction,
      });
    });
  });
}

async function runModelAction({ model, node, action }) {
  try {
    if (action === "logs") {
      const title = node ? `${node} / ${model}` : model;
      const fallbackPath = node
        ? `/nodes/${encodeURIComponent(node)}/logs/${encodeURIComponent(model)}?lines=200`
        : `/logs/${encodeURIComponent(model)}?lines=200`;
      const streamPath = node
        ? `/nodes/${encodeURIComponent(node)}/logs/${encodeURIComponent(model)}/stream?lines=200`
        : `/logs/${encodeURIComponent(model)}/stream?lines=200`;
      await streamLogsIntoModal({ title, streamPath, fallbackPath, emptyText: "No log output." });
      return;
    }

    const path = node
      ? `/nodes/${encodeURIComponent(node)}/models/${encodeURIComponent(model)}/${action}`
      : `/models/${encodeURIComponent(model)}/${action}`;
    if (["stop", "restart"].includes(action)) {
      if (!confirmAction(`Confirm ${action} for ${node ? `${node} / ` : ""}${model}?`)) return;
      if (shouldDryRun()) {
        await writeAuditEvent({
          actor: "ui",
          event_type: "model_action",
          dry_run: true,
          target: `${node ? `${node}/` : ""}${model}`,
          route: node ? `node:${node}` : "local",
          payload: { action, path },
        });
        $("log-title").textContent = "dry-run model action";
        $("log-output").textContent = JSON.stringify({ method: "POST", path }, null, 2);
        openLogModal();
        showToast("Dry run only: request not sent");
        return;
      }
    }
    await writeAuditEvent({
      actor: "ui",
      event_type: "model_action",
      dry_run: false,
      target: `${node ? `${node}/` : ""}${model}`,
      route: node ? `node:${node}` : "local",
      payload: { action, path },
    });
    await api(path, { method: "POST" });
    showToast(`${action} sent for ${node ? `${node} / ` : ""}${model}`);
    await refreshAll();
  } catch (error) {
    showToast(error.message);
  }
}

async function runConversionAction({ model, action }) {
  try {
    if (action === "logs") {
      await streamLogsIntoModal({
        title: `conversion / ${model}`,
        streamPath: `/conversions/${encodeURIComponent(model)}/logs/stream?lines=200`,
        fallbackPath: `/conversions/${encodeURIComponent(model)}/logs?lines=200`,
        emptyText: "No conversion log output.",
      });
      return;
    }

    await api(`/conversions/${encodeURIComponent(model)}/start`, { method: "POST" });
    showToast(`conversion started for ${model}`);
    await refreshAll();
  } catch (error) {
    showToast(error.message);
  }
}

async function runQuantizationAction({ fileId, filename, type, action }) {
  try {
    if (action === "logs") {
      await streamLogsIntoModal({
        title: `quantization / ${filename}`,
        streamPath: `/quantizations/${encodeURIComponent(fileId)}/logs/stream?lines=200`,
        fallbackPath: `/quantizations/${encodeURIComponent(fileId)}/logs?lines=200`,
        emptyText: "No quantization log output.",
      });
      return;
    }

    await api(`/quantizations/${encodeURIComponent(fileId)}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ type }),
    });
    showToast(`quantization started for ${filename}`);
    await refreshAll();
  } catch (error) {
    showToast(error.message);
  }
}

async function addLibraryModel({ fileId, modelName }) {
  const port = Number($("library-port").value || 8080);
  const ctx = Number($("library-ctx").value || 8192);
  const gpuLayers = Number($("library-gpu-layers").value || 999);
  const reasoning = $("library-reasoning").value || "auto";
  const reasoningBudget = Number($("library-reasoning-budget").value || 2048);
  const name = (modelName || "").trim();
  if (!name) {
    showToast("Enter a model name.");
    return false;
  }
  try {
    await api(`/library/ggufs/${encodeURIComponent(fileId)}/add-model`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        name,
        port,
        ctx,
        gpu_layers: gpuLayers,
        host: "0.0.0.0",
        reasoning,
        reasoning_budget: reasoningBudget,
      }),
    });
    $("library-port").value = String(port + 1);
    showToast(`added ${name} as local model`);
    await refreshAll();
    return true;
  } catch (error) {
    showToast(error.message);
    return false;
  }
}

async function addSelectedGgufModel() {
  const file = state.ggufFiles.find((item) => item.id === state.selectedGgufId);
  if (!file) return showToast("Select a GGUF file first.");
  const added = await addLibraryModel({
    fileId: file.id,
    modelName: $("library-model-name").value || suggestedGgufModelName(file),
  });
  if (added) closeModal($("gguf-detail-modal"));
}

async function deleteSelectedGguf() {
  const file = state.ggufFiles.find((item) => item.id === state.selectedGgufId);
  if (!file) return showToast("Select a GGUF file first.");
  const unregisterText = file.registered_as ? ` and unregister "${file.registered_as}"` : "";
  if (!confirmAction(`Delete ${file.filename} from disk${unregisterText}? This cannot be undone.`)) {
    return;
  }

  try {
    const deleted = await api(`/library/ggufs/${encodeURIComponent(file.id)}`, { method: "DELETE" });
    const unregistered = deleted.unregistered_models?.length
      ? ` and unregistered ${deleted.unregistered_models.join(", ")}`
      : "";
    closeModal($("gguf-detail-modal"));
    showToast(`deleted ${file.filename}${unregistered}`);
    await refreshAll();
  } catch (error) {
    showToast(error.message);
  }
}

async function removeSelectedGgufModel() {
  const file = state.ggufFiles.find((item) => item.id === state.selectedGgufId);
  if (!file) return showToast("Select a GGUF file first.");
  if (!file.registered_as) return showToast("No registered model to remove for this file.");
  if (!confirmAction(`Remove model "${file.registered_as}" from configured local models?`)) return;
  try {
    await api(`/library/models/${encodeURIComponent(file.registered_as)}`, { method: "DELETE" });
    closeModal($("gguf-detail-modal"));
    showToast(`removed model ${file.registered_as}`);
    await refreshAll();
  } catch (error) {
    showToast(error.message);
  }
}

async function sendChat() {
  if (state.chatPending) {
    showToast("Wait for the current chat response to finish.");
    return;
  }
  const model = $("chat-model").value;
  const target = $("chat-target").value || "auto";
  const content = $("chat-input").value.trim();
  const imageInput = $("chat-image-input");
  const imageFile = imageInput?.files?.[0] || null;
  if (!model) {
    showToast("Select a model before chatting.");
    return;
  }
  if (!content && !imageFile) {
    showToast("Enter a prompt or attach an image first.");
    return;
  }

  const routeMeta = buildRouteMeta(model, target);
  const pendingMessage = { role: "assistant", content: "", pending: true, routeMeta };
  const imageDataUrl = imageFile ? await fileToDataUrl(imageFile) : null;
  const userContent = imageDataUrl
    ? [
        ...(content ? [{ type: "text", text: content }] : []),
        { type: "image_url", image_url: { url: imageDataUrl } },
      ]
    : content;
  state.lastUserPrompt = content;
  state.chatMessages.push(
    { role: "user", content: content || "(image input)", routeMeta, hasImage: Boolean(imageDataUrl) },
    pendingMessage
  );
  state.chatPending = true;
  $("chat-input").value = "";
  renderChatTranscript();
  $("send-chat-button").disabled = true;
  $("chat-stop-button").disabled = false;
  $("chat-regenerate-button").disabled = true;
  $("chat-state").textContent = "Streaming response...";

  try {
    const structured = parseStructuredOutput();
    if (structured.error) {
      showToast(structured.error);
      $("chat-structured-validation").textContent = structured.error;
      state.chatMessages = state.chatMessages.slice(0, -2);
      state.chatPending = false;
      renderChatTranscript();
      $("send-chat-button").disabled = false;
      $("chat-stop-button").disabled = true;
      $("chat-state").textContent = "Ready";
      return;
    }
    const payload = {
      messages: state.chatMessages
        .filter((message) => !message.pending && message.role !== "error")
        .map((message, index, arr) => ({
          role: message.role,
          content:
            imageDataUrl && message.hasImage && index === arr.length - 1 ? userContent : message.content,
        })),
      temperature: Number($("chat-temperature").value || 0.7),
      max_tokens: Number($("chat-max-tokens").value || 512),
      top_p: Number($("chat-top-p").value || 1.0),
      top_k: Number($("chat-top-k").value || 40),
      min_p: Number($("chat-min-p").value || 0.0),
      repeat_penalty: Number($("chat-repeat-penalty").value || 1.1),
      seed: Number($("chat-seed").value || -1),
      stop: parseStopTokens($("chat-stop").value || ""),
      reasoning: $("chat-reasoning").checked,
      cache_prompt: $("chat-cache-prompt").checked,
      slot_id: $("chat-slot-id").value ? Number($("chat-slot-id").value) : null,
      ...(structured.payload || {}),
      target,
    };
    pendingMessage.startedAtMs = performance.now();
    pendingMessage.requestPayload = payload;
    pendingMessage.lineage = {
      model,
      target,
      model_config_hash: state.chatCapabilities?.model_config_hash || null,
      capability_snapshot: {
        chat: state.chatCapabilities?.supports || null,
        kv: state.kvCapabilities?.supports || null,
      },
    };
    await requestChatCompletion(model, payload, pendingMessage);
    pendingMessage.content = pendingMessage.content || "(empty response)";
    pendingMessage.pending = false;
  } catch (error) {
    if (error?.name === "AbortError") {
      pendingMessage.content = pendingMessage.content || "(stopped)";
      pendingMessage.pending = false;
      pendingMessage.stopped = true;
      return;
    }
    pendingMessage.role = "error";
    pendingMessage.content = error.message;
    pendingMessage.pending = false;
  } finally {
    state.chatPending = false;
    state.chatAbortController = null;
    renderChatTranscript();
    $("send-chat-button").disabled = false;
    $("chat-stop-button").disabled = true;
    $("chat-regenerate-button").disabled = !state.lastUserPrompt;
    $("chat-state").textContent = "Ready";
  }
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Failed to read image file"));
    reader.readAsDataURL(file);
  });
}

async function requestChatCompletion(model, payload, pendingMessage) {
  state.chatAbortController = new AbortController();
  const request = {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(payload),
    signal: state.chatAbortController.signal,
  };
  try {
    const streamResult = await fetchStream(`/chat/${encodeURIComponent(model)}/stream`, request);
    const route = streamResult.response.headers.get("X-Llama-Manager-Route");
    if (route) {
      pendingMessage.routeMeta = { ...(pendingMessage.routeMeta || {}), resolved: route };
    }
    const reader = streamResult.reader;
    await readChatStream(reader, pendingMessage);
  } catch (error) {
    if (error.status !== 404) {
      throw error;
    }
    $("chat-state").textContent = "Streaming unavailable; using standard response...";
    const response = await fetch(`/chat/${encodeURIComponent(model)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`${response.status} ${response.statusText}: ${text}`);
    }
    const route = response.headers.get("X-Llama-Manager-Route");
    if (route) {
      pendingMessage.routeMeta = { ...(pendingMessage.routeMeta || {}), resolved: route };
    }
    const body = await response.json();
    applyChatCompletion(body, pendingMessage);
  }
}

function stopChatGeneration() {
  if (!state.chatPending || !state.chatAbortController) {
    return;
  }
  state.chatAbortController.abort();
}

async function regenerateLastResponse() {
  if (state.chatPending) {
    showToast("Wait for the current chat response to finish.");
    return;
  }
  const model = $("chat-model").value;
  const content = state.lastUserPrompt || "";
  if (!model || !content) {
    showToast("No previous prompt to regenerate.");
    return;
  }
  $("chat-input").value = content;
  await sendChat();
}

function applyChatCompletion(response, pendingMessage) {
  const choice = response.choices?.[0];
  const message = choice?.message || {};
  pendingMessage.role = message.role || "assistant";
  pendingMessage.reasoningContent = message.reasoning_content || "";
  pendingMessage.content = message.content || "";
  if (!pendingMessage.firstTokenAtMs && (pendingMessage.content || pendingMessage.reasoningContent)) {
    pendingMessage.firstTokenAtMs = performance.now();
  }
  applyTelemetryFromChunk(response, pendingMessage);
  finalizeTelemetry(pendingMessage);
  if (choice?.finish_reason === "length" && !pendingMessage.content) {
    pendingMessage.content = "(hit max tokens before producing a final answer)";
  }
}

async function readChatStream(reader, pendingMessage) {
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const event of events) {
      appendChatStreamEvent(event, pendingMessage);
    }

    if (done) {
      if (buffer.trim()) {
        appendChatStreamEvent(buffer, pendingMessage);
      }
      break;
    }
  }
}

function appendChatStreamEvent(event, pendingMessage) {
  const dataLines = event
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim());

  for (const data of dataLines) {
    if (!data || data === "[DONE]") {
      continue;
    }
    try {
      const chunk = JSON.parse(data);
      applyTelemetryFromChunk(chunk, pendingMessage);
      const choice = chunk.choices?.[0];
      const delta = choice?.delta || {};
      const content = delta.content || choice?.text || "";
      const reasoning = delta.reasoning_content || choice?.message?.reasoning_content || "";
      if (delta.role) {
        pendingMessage.role = delta.role;
      }
      if (reasoning) {
        if (!pendingMessage.firstTokenAtMs) pendingMessage.firstTokenAtMs = performance.now();
        pendingMessage.reasoningContent = `${pendingMessage.reasoningContent || ""}${reasoning}`;
        renderChatTranscript();
      }
      if (content) {
        if (!pendingMessage.firstTokenAtMs) pendingMessage.firstTokenAtMs = performance.now();
        pendingMessage.content += content;
        renderChatTranscript();
      }
      if (choice?.finish_reason === "length" && !pendingMessage.content) {
        pendingMessage.content = "(hit max tokens before producing a final answer)";
      }
    } catch (error) {
      pendingMessage.content += data;
      renderChatTranscript();
    }
  }
}

function clearChat() {
  if (state.chatPending) {
    showToast("Wait for the current chat response to finish.");
    return;
  }
  clearActiveChatSessionSelection();
  state.chatMessages = [];
  renderChatTranscript();
  showToast("Started a new chat");
}

function renderChatTranscript() {
  const transcript = $("chat-transcript");
  if (!state.chatMessages.length) {
    transcript.innerHTML = `<p class="empty">Start a running model, choose it here, and send a test prompt.</p>`;
    return;
  }

  transcript.innerHTML = state.chatMessages
    .map(
      (message) => `<div class="chat-message ${escapeHtml(message.role)}${message.pending ? " pending" : ""}">
        <span class="chat-role">${escapeHtml(message.role)}</span>
        ${renderRouteMeta(message)}
        ${renderReasoning(message)}
        <p>${escapeHtml(message.content || (message.pending ? "Streaming..." : ""))}${
          message.pending ? ` <span class="typing-dots"><span></span><span></span><span></span></span>` : ""
        }</p>
        ${renderChatMessageActions(message)}
      </div>`
    )
    .join("");
  bindChatMessageActions(transcript);
  transcript.scrollTop = transcript.scrollHeight;
}

function renderRouteMeta(message) {
  const meta = message.routeMeta;
  if (!meta) return "";
  const chips = [
    `model: ${meta.model}`,
    `target: ${meta.target}`,
    meta.resolved ? `via: ${meta.resolved}` : null,
    message.telemetry?.tokensPerSecond != null ? `tok/s: ${message.telemetry.tokensPerSecond.toFixed(2)}` : null,
    message.telemetry?.ttftMs != null ? `ttft: ${message.telemetry.ttftMs.toFixed(0)}ms` : null,
    message.telemetry?.totalMs != null ? `total: ${message.telemetry.totalMs.toFixed(0)}ms` : null,
    message.telemetry?.promptTokens != null ? `prompt_toks: ${message.telemetry.promptTokens}` : null,
    message.telemetry?.completionTokens != null ? `gen_toks: ${message.telemetry.completionTokens}` : null,
    message.lineage?.capability_snapshot ? "lineage:yes" : null,
  ].filter(Boolean);
  return `<div class="chat-chips">${chips
    .map((chip) => `<span class="chat-chip">${escapeHtml(chip)}</span>`)
    .join("")}</div>`;
}

function buildRouteMeta(model, target) {
  const normalizedTarget = target || "auto";
  const resolved =
    normalizedTarget === "local"
      ? "local"
      : normalizedTarget.startsWith("node:")
        ? normalizedTarget.slice(5)
        : "auto";
  return { model, target: normalizedTarget, resolved };
}

function applyChatPreset() {
  const selected = $("chat-preset").value;
  localStorage.setItem(CHAT_PRESET_STORAGE_KEY, selected);
  const preset = CHAT_PRESETS[selected] || CHAT_PRESETS.balanced;
  $("chat-temperature").value = String(preset.temperature);
  $("chat-top-p").value = String(preset.top_p);
  $("chat-top-k").value = String(preset.top_k);
  $("chat-min-p").value = String(preset.min_p);
  $("chat-repeat-penalty").value = String(preset.repeat_penalty);
  $("chat-seed").value = String(preset.seed);
  renderChatDefaultsDiff();
}

function restoreChatPreset() {
  const select = $("chat-preset");
  if (!select) return;
  const stored = localStorage.getItem(CHAT_PRESET_STORAGE_KEY) || "balanced";
  if ([...select.options].some((option) => option.value === stored)) {
    select.value = stored;
  }
  applyChatPreset();
}

function renderChatDefaultsDiff() {
  const defaults = CHAT_PRESETS.balanced;
  const maxTokensDefault = 512;
  const stopDefault = null;
  const pairs = [
    ["temperature", Number($("chat-temperature").value || defaults.temperature)],
    ["max_tokens", Number($("chat-max-tokens").value || maxTokensDefault)],
    ["top_p", Number($("chat-top-p").value || defaults.top_p)],
    ["top_k", Number($("chat-top-k").value || defaults.top_k)],
    ["min_p", Number($("chat-min-p").value || defaults.min_p)],
    ["repeat_penalty", Number($("chat-repeat-penalty").value || defaults.repeat_penalty)],
    ["seed", Number($("chat-seed").value || defaults.seed)],
    ["stop", parseStopTokens($("chat-stop").value || "")],
  ];
  const changed = pairs.filter(([key, value]) => {
    if (key === "max_tokens") return value !== maxTokensDefault;
    if (key === "stop") return JSON.stringify(value) !== JSON.stringify(stopDefault);
    return value !== defaults[key];
  });
  $("chat-default-diff").textContent = changed.length
    ? `Overrides: ${changed.map(([k, v]) => `${k}=${v}`).join(", ")}`
    : "Using default chat settings";
}

function renderReasoning(message) {
  if (!message.reasoningContent) {
    return "";
  }
  return `<details class="chat-reasoning" ${message.pending ? "open" : ""}>
    <summary>Reasoning</summary>
    <pre>${escapeHtml(message.reasoningContent)}</pre>
  </details>`;
}

function renderChatMessageActions(message) {
  if (message.role !== "assistant" || message.pending || !message.content) {
    return "";
  }
  const repro = buildReproBundle(message);
  return `<div class="chat-meta">
    <button class="chat-inline-action" data-chat-copy="${escapeHtml(message.content)}" type="button">Copy</button>
    <button class="chat-inline-action" data-chat-repro="${escapeHtml(JSON.stringify(repro))}" type="button">Copy Repro JSON</button>
    <button class="chat-inline-action" data-chat-rerun="${escapeHtml(JSON.stringify(message.requestPayload || {}))}" data-chat-rerun-model="${escapeHtml(message.lineage?.model || message.routeMeta?.model || '')}" type="button">Rerun exact</button>
  </div>`;
}

function bindChatMessageActions(root) {
  root.querySelectorAll("[data-chat-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const text = button.getAttribute("data-chat-copy") || "";
      try {
        await navigator.clipboard.writeText(text);
        showToast("Response copied");
      } catch (error) {
        showToast("Clipboard copy failed");
      }
    });
  });
  root.querySelectorAll("[data-chat-repro]").forEach((button) => {
    button.addEventListener("click", async () => {
      const text = button.getAttribute("data-chat-repro") || "";
      try {
        await navigator.clipboard.writeText(text);
        showToast("Repro JSON copied");
      } catch (error) {
        showToast("Clipboard copy failed");
      }
    });
  });
  root.querySelectorAll("[data-chat-rerun]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (state.chatPending) return showToast("Wait for current response first.");
      const model = button.getAttribute("data-chat-rerun-model") || $("chat-model").value;
      const text = button.getAttribute("data-chat-rerun") || "{}";
      let payload = {};
      try {
        payload = JSON.parse(text);
      } catch (_error) {
        return showToast("Invalid rerun payload");
      }
      if (!model || !payload.messages) return showToast("Missing rerun model/payload");
      const routeMeta = buildRouteMeta(model, payload.target || "auto");
      const pendingMessage = { role: "assistant", content: "", pending: true, routeMeta };
      pendingMessage.startedAtMs = performance.now();
      pendingMessage.requestPayload = payload;
      pendingMessage.lineage = {
        model,
        target: payload.target || "auto",
        model_config_hash: state.chatCapabilities?.model_config_hash || null,
        capability_snapshot: {
          chat: state.chatCapabilities?.supports || null,
          kv: state.kvCapabilities?.supports || null,
        },
      };
      state.chatMessages.push(pendingMessage);
      state.chatPending = true;
      renderChatTranscript();
      try {
        await requestChatCompletion(model, payload, pendingMessage);
        pendingMessage.content = pendingMessage.content || "(empty response)";
      } catch (error) {
        pendingMessage.role = "error";
        pendingMessage.content = error.message;
      } finally {
        pendingMessage.pending = false;
        state.chatPending = false;
        state.chatAbortController = null;
        renderChatTranscript();
      }
    });
  });
}

function parseStopTokens(value) {
  const normalized = String(value || "").trim();
  if (!normalized) return null;
  const tokens = normalized
    .split(",")
    .map((token) => token.trim())
    .filter(Boolean);
  if (!tokens.length) return null;
  return tokens.length === 1 ? tokens[0] : tokens;
}

function parseStructuredOutput() {
  const mode = $("chat-structured-mode")?.value || "none";
  const schemaRaw = ($("chat-json-schema")?.value || "").trim();
  const grammarRaw = ($("chat-grammar")?.value || "").trim();

  if (mode === "none") return { payload: {} };
  if (mode === "json_schema") {
    if (!schemaRaw) return { error: "Structured mode is JSON Schema but schema is empty." };
    try {
      const parsed = JSON.parse(schemaRaw);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return { error: "JSON Schema must be a JSON object." };
      }
      return { payload: { json_schema: parsed } };
    } catch (_error) {
      return { error: "Invalid JSON Schema JSON." };
    }
  }
  if (mode === "grammar") {
    if (!grammarRaw) return { error: "Structured mode is Grammar but grammar is empty." };
    return { payload: { grammar: grammarRaw } };
  }
  return { payload: {} };
}

function buildReproBundle(message) {
  return {
    created_at: new Date().toISOString(),
    route: message.routeMeta || null,
    request: message.requestPayload || null,
    messages: state.chatMessages
      .filter((item) => !item.pending && item.role !== "error")
      .map((item) => ({ role: item.role, content: item.content })),
    response: {
      role: message.role,
      content: message.content,
      reasoning_content: message.reasoningContent || "",
      telemetry: message.telemetry || null,
      lineage: message.lineage || null,
    },
  };
}

function buildCurrentChatPayload() {
  const structured = parseStructuredOutput();
  return {
    messages: state.chatMessages
      .filter((message) => !message.pending && message.role !== "error")
      .map((message) => ({ role: message.role, content: message.content })),
    temperature: Number($("chat-temperature").value || 0.7),
    max_tokens: Number($("chat-max-tokens").value || 512),
    top_p: Number($("chat-top-p").value || 1.0),
    top_k: Number($("chat-top-k").value || 40),
    min_p: Number($("chat-min-p").value || 0.0),
    repeat_penalty: Number($("chat-repeat-penalty").value || 1.1),
    seed: Number($("chat-seed").value || -1),
    stop: parseStopTokens($("chat-stop").value || ""),
    reasoning: $("chat-reasoning").checked,
    cache_prompt: $("chat-cache-prompt").checked,
    slot_id: $("chat-slot-id").value ? Number($("chat-slot-id").value) : null,
    ...(structured.payload || {}),
    target: $("chat-target").value || "auto",
  };
}

function currentChatDefaults() {
  const structured = parseStructuredOutput();
  const structuredMode = $("chat-structured-mode")?.value || "none";
  return {
    temperature: Number($("chat-temperature").value || 0.7),
    max_tokens: Number($("chat-max-tokens").value || 512),
    top_p: Number($("chat-top-p").value || 1.0),
    top_k: Number($("chat-top-k").value || 40),
    min_p: Number($("chat-min-p").value || 0.0),
    repeat_penalty: Number($("chat-repeat-penalty").value || 1.1),
    seed: Number($("chat-seed").value || -1),
    stop: parseStopTokens($("chat-stop").value || ""),
    reasoning: $("chat-reasoning").checked,
    cache_prompt: $("chat-cache-prompt").checked,
    slot_id: $("chat-slot-id").value ? Number($("chat-slot-id").value) : null,
    structured_mode: structuredMode,
    json_schema_text: $("chat-json-schema")?.value || "",
    grammar_text: $("chat-grammar")?.value || "",
    ...(structured.payload || {}),
  };
}

function applyStructuredModeUI() {
  const mode = $("chat-structured-mode")?.value || "none";
  const schemaEl = $("chat-json-schema");
  const grammarEl = $("chat-grammar");
  if (!schemaEl || !grammarEl) return;
  schemaEl.disabled = mode !== "json_schema";
  grammarEl.disabled = mode !== "grammar";
  const result = parseStructuredOutput();
  $("chat-structured-validation").textContent =
    result.error || (mode === "none" ? "Structured output disabled" : `Structured output ready: ${mode}`);
}

async function saveChatSession({ saveAsNew = false } = {}) {
  const name = ($("chat-session-name").value || "").trim();
  if (!name) return showToast("Enter a session name.");
  const model = $("chat-model").value;
  if (!model) return showToast("Select a model.");
  const payload = buildChatSessionSavePayload({
    name,
    model,
    target: $("chat-target").value || "auto",
    messages: state.chatMessages.filter((m) => !m.pending && m.role !== "error").map((m) => ({ role: m.role, content: String(m.content || "") })),
    requestDefaults: currentChatDefaults(),
    selectedSessionId: saveAsNew ? "" : state.selectedChatSessionId,
    saveAsNew,
  });
  const saved = await api("/chat/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  state.selectedChatSessionId = nextSelectedChatSessionId({
    savedSessionId: saved?.id || "",
    saveAsNew,
  });
  persistActiveChatSessionId(state.selectedChatSessionId);
  showToast(saveAsNew ? "Session saved as new" : "Session saved");
  await refreshChatSessions();
}

async function loadChatSession({ sessionId = "", silent = false } = {}) {
  const id = sessionId || $("chat-session-select").value;
  if (!id) return showToast("Select a saved session.");
  const session = await api(`/chat/sessions/${encodeURIComponent(id)}`);
  state.selectedChatSessionId = id;
  persistActiveChatSessionId(id);
  $("chat-session-select").value = id;
  $("chat-session-name").value = session.name || "";
  $("chat-model").value = session.model || $("chat-model").value;
  $("chat-target").value = session.target_selector || "auto";
  const defaults = session.request_defaults || {};
  if (defaults.temperature != null) $("chat-temperature").value = String(defaults.temperature);
  if (defaults.max_tokens != null) $("chat-max-tokens").value = String(defaults.max_tokens);
  if (defaults.top_p != null) $("chat-top-p").value = String(defaults.top_p);
  if (defaults.top_k != null) $("chat-top-k").value = String(defaults.top_k);
  if (defaults.min_p != null) $("chat-min-p").value = String(defaults.min_p);
  if (defaults.repeat_penalty != null) $("chat-repeat-penalty").value = String(defaults.repeat_penalty);
  if (defaults.seed != null) $("chat-seed").value = String(defaults.seed);
  if (defaults.stop != null) {
    if (Array.isArray(defaults.stop)) $("chat-stop").value = defaults.stop.join(", ");
    else $("chat-stop").value = String(defaults.stop);
  } else {
    $("chat-stop").value = "";
  }
  $("chat-reasoning").checked = Boolean(defaults.reasoning);
  $("chat-cache-prompt").checked = defaults.cache_prompt !== false;
  $("chat-slot-id").value = defaults.slot_id != null ? String(defaults.slot_id) : "";
  $("chat-json-schema").value = String(defaults.json_schema_text || "");
  $("chat-grammar").value = String(defaults.grammar_text || "");
  const mode = String(defaults.structured_mode || "none");
  if ([...$("chat-structured-mode").options].some((option) => option.value === mode && !option.disabled)) {
    $("chat-structured-mode").value = mode;
  } else {
    $("chat-structured-mode").value = "none";
  }
  applyStructuredModeUI();
  state.chatMessages = (session.messages || []).map((m) => ({ role: m.role, content: m.content }));
  renderChatDefaultsDiff();
  renderChatTranscript();
  if (!silent) {
    showToast("Session loaded");
  }
}

async function runEmbeddings() {
  const model = $("embeddings-model").value;
  const target = $("embeddings-target").value || "auto";
  const lines = String($("embeddings-input").value || "").split("\n").map((s) => s.trim()).filter(Boolean);
  if (!model) return showToast("Select an embeddings model.");
  if (!lines.length) return showToast("Enter at least one line.");
  const result = await api(`/chat/${encodeURIComponent(model)}/embeddings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input: lines, target }),
  });
  state.lastEmbeddingsResult = result;
  const rows = (result.data || []).map((row, idx) => {
    const emb = row.embedding || [];
    const usage = result.usage
      ? `prompt=${result.usage.prompt_tokens ?? "-"}, total=${result.usage.total_tokens ?? "-"}`
      : "-";
    return `<tr>
      <td>${idx}</td>
      <td>${escapeHtml(String(row.id ?? idx))}</td>
      <td>${escapeHtml(String(row.object ?? "-"))}</td>
      <td>${escapeHtml(String(result.model ?? row.model ?? "-"))}</td>
      <td>${emb.length}</td>
      <td>${escapeHtml(usage)}</td>
      <td class="path">${escapeHtml(JSON.stringify(emb.slice(0, 8)))}${emb.length > 8 ? " ..." : ""}</td>
    </tr>`;
  });
  $("embeddings-body").innerHTML = rows.join("") || `<tr><td colspan="7" class="empty">No vectors returned.</td></tr>`;
}

function downloadText(filename, text, mime) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function exportEmbeddingsJson() {
  if (!state.lastEmbeddingsResult) return showToast("Run embeddings first.");
  downloadText("embeddings.json", JSON.stringify(state.lastEmbeddingsResult, null, 2), "application/json");
}

function exportEmbeddingsCsv() {
  if (!state.lastEmbeddingsResult) return showToast("Run embeddings first.");
  const rows = ["index,id,object,model,dimensions,prompt_tokens,total_tokens,vector_preview"];
  const usage = state.lastEmbeddingsResult.usage || {};
  (state.lastEmbeddingsResult.data || []).forEach((row, i) => {
    const emb = row.embedding || [];
    rows.push(
      `${i},${JSON.stringify(row.id ?? i)},${JSON.stringify(row.object ?? "")},${JSON.stringify(state.lastEmbeddingsResult.model ?? row.model ?? "")},${emb.length},${usage.prompt_tokens ?? ""},${usage.total_tokens ?? ""},"${(emb.slice(0, 8).join(" ")).replaceAll('"', '""')}"`
    );
  });
  downloadText("embeddings.csv", rows.join("\n"), "text/csv");
}

function getEmbeddingVectors() {
  return (state.lastEmbeddingsResult?.data || []).map((row) => row.embedding || []);
}

function cosineSimilarity(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length || a.length === 0) return 0;
  let dot = 0;
  let na = 0;
  let nb = 0;
  for (let i = 0; i < a.length; i += 1) {
    const av = Number(a[i] || 0);
    const bv = Number(b[i] || 0);
    dot += av * bv;
    na += av * av;
    nb += bv * bv;
  }
  if (na === 0 || nb === 0) return 0;
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}

function computeSimilarityTable() {
  const vectors = getEmbeddingVectors();
  if (!vectors.length) return showToast("Run embeddings first.");
  const anchor = Number($("embeddings-anchor-index").value || 0);
  if (!Number.isInteger(anchor) || anchor < 0 || anchor >= vectors.length) {
    return showToast("Anchor index out of range.");
  }
  const rows = vectors
    .map((v, i) => ({
      i,
      id: state.lastEmbeddingsResult.data?.[i]?.id ?? i,
      score: cosineSimilarity(vectors[anchor], v),
    }))
    .sort((a, b) => b.score - a.score)
    .map((item, rank) => `<tr><td>${rank + 1}</td><td>${item.i}</td><td>${escapeHtml(String(item.id))}</td><td>${item.score.toFixed(6)}</td></tr>`)
    .join("");
  $("embeddings-similarity-body").innerHTML = rows || `<tr><td colspan="4" class="empty">No data.</td></tr>`;
}

function computeNearestNeighbors() {
  const vectors = getEmbeddingVectors();
  if (!vectors.length) return showToast("Run embeddings first.");
  const anchor = Number($("embeddings-anchor-index").value || 0);
  if (!Number.isInteger(anchor) || anchor < 0 || anchor >= vectors.length) {
    return showToast("Anchor index out of range.");
  }
  const neighbors = vectors
    .map((v, i) => ({ i, id: state.lastEmbeddingsResult.data?.[i]?.id ?? i, score: cosineSimilarity(vectors[anchor], v) }))
    .filter((x) => x.i !== anchor)
    .sort((a, b) => b.score - a.score)
    .slice(0, 10);
  $("embeddings-similarity-body").innerHTML = neighbors
    .map((item, rank) => `<tr><td>${rank + 1}</td><td>${item.i}</td><td>${escapeHtml(String(item.id))}</td><td>${item.score.toFixed(6)}</td></tr>`)
    .join("") || `<tr><td colspan="4" class="empty">No neighbors found.</td></tr>`;
}

function runQuickClusters() {
  const vectors = getEmbeddingVectors();
  if (!vectors.length) return showToast("Run embeddings first.");
  const k = Math.min(3, vectors.length);
  const centroids = vectors.slice(0, k).map((v) => [...v]);
  const assignments = new Array(vectors.length).fill(0);
  for (let iter = 0; iter < 5; iter += 1) {
    for (let i = 0; i < vectors.length; i += 1) {
      let best = 0;
      let bestScore = -Infinity;
      for (let c = 0; c < k; c += 1) {
        const score = cosineSimilarity(vectors[i], centroids[c]);
        if (score > bestScore) {
          bestScore = score;
          best = c;
        }
      }
      assignments[i] = best;
    }
    for (let c = 0; c < k; c += 1) {
      const members = vectors.filter((_, idx) => assignments[idx] === c);
      if (!members.length) continue;
      const mean = new Array(members[0].length).fill(0);
      for (const vec of members) {
        for (let j = 0; j < vec.length; j += 1) mean[j] += Number(vec[j] || 0);
      }
      for (let j = 0; j < mean.length; j += 1) mean[j] /= members.length;
      centroids[c] = mean;
    }
  }
  const summary = [];
  for (let c = 0; c < k; c += 1) {
    const members = assignments
      .map((cluster, idx) => ({ cluster, idx }))
      .filter((row) => row.cluster === c)
      .map((row) => row.idx);
    summary.push({ cluster: c, size: members.length, members });
  }
  $("embeddings-cluster-output").textContent = JSON.stringify(summary, null, 2);
}

function quantTypeBits(type) {
  const t = String(type || "").toUpperCase();
  if (t.startsWith("Q2")) return 2.5;
  if (t.startsWith("Q3")) return 3.5;
  if (t.startsWith("Q4")) return 4.5;
  if (t.startsWith("Q5")) return 5.5;
  if (t.startsWith("Q6")) return 6.5;
  if (t.startsWith("Q8")) return 8.5;
  if (t.includes("F16")) return 16;
  return 6;
}

function estimateQuantSizeGb(sourceGb, type) {
  const bits = quantTypeBits(type);
  return sourceGb * (bits / 16);
}

function throughputFactor(type) {
  const bits = quantTypeBits(type);
  return Number((16 / bits).toFixed(2));
}

function recommendQuantization() {
  const vramGb = Number($("advisor-vram-gb").value || 16);
  const latencyGoal = $("advisor-latency-goal").value || "balanced";
  const qualityGoal = $("advisor-quality-goal").value || "balanced";
  const files = state.quantizations || [];
  if (!files.length) return showToast("No quantization files loaded.");

  const candidates = [];
  for (const file of files) {
    const sourceGb = Number(file.size_gb || 0);
    const types = Array.isArray(file.supported_types) ? file.supported_types : [];
    for (const type of types) {
      const estSizeGb = estimateQuantSizeGb(sourceGb, type);
      const fits = estSizeGb <= vramGb * 0.85;
      let score = 0;
      score += fits ? 20 : -50;
      if (latencyGoal === "low") score += throughputFactor(type) * 8;
      if (latencyGoal === "balanced") score += throughputFactor(type) * 4;
      if (qualityGoal === "high") score += quantTypeBits(type) * 1.8;
      if (qualityGoal === "max") score += quantTypeBits(type) * 2.6;
      if (qualityGoal === "balanced") score += quantTypeBits(type) * 1.2;
      candidates.push({
        file: file.filename,
        type,
        source_gb: Number(sourceGb.toFixed(2)),
        est_size_gb: Number(estSizeGb.toFixed(2)),
        throughput_factor: throughputFactor(type),
        fits_vram: fits,
        score: Number(score.toFixed(2)),
      });
    }
  }
  candidates.sort((a, b) => b.score - a.score);
  const top = candidates.slice(0, 5);
  const best = top[0] || null;
  $("advisor-output").textContent = JSON.stringify(
    {
      inputs: { vram_gb: vramGb, latency_goal: latencyGoal, quality_goal: qualityGoal },
      recommendation: best,
      top_candidates: top,
      notes: [
        "Memory estimate approximates quant bits vs FP16 baseline and is not exact.",
        "Throughput factor is a relative heuristic, not measured tokens/sec.",
      ],
    },
    null,
    2
  );
}

async function deleteChatSession() {
  const id = $("chat-session-select").value;
  if (!id) return showToast("Select a saved session.");
  await api(`/chat/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (state.selectedChatSessionId === id) {
    clearActiveChatSessionSelection();
  }
  showToast("Session deleted");
  await refreshChatSessions();
}

async function inspectChatPrompt() {
  const model = $("chat-model").value;
  if (!model) return showToast("Select a model before inspecting prompt/template.");
  const payload = buildCurrentChatPayload();
  if (!payload.messages.length) return showToast("Add at least one chat message first.");
  try {
    const result = await api(`/chat/${encodeURIComponent(model)}/inspect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    $("chat-inspect-summary").textContent =
      `Estimated prompt tokens: ${result.estimated_prompt_tokens} (${result.estimation_method})`;
    $("log-title").textContent = `prompt/template inspector / ${model}`;
    $("log-output").textContent = result.rendered_prompt_preview || "(empty)";
    openLogModal();
  } catch (error) {
    showToast(error.message);
  }
}

async function refreshKvSlots() {
  const model = $("chat-model").value;
  const target = $("chat-target").value || "auto";
  if (!model) return showToast("Select a model first.");
  try {
    const payload = await api(`/chat/${encodeURIComponent(model)}/kv/slots?target=${encodeURIComponent(target)}`);
    $("log-title").textContent = `kv slots / ${model}`;
    $("log-output").textContent = JSON.stringify(payload, null, 2);
    openLogModal();
    const clearSupported = state.kvCapabilities?.supports?.clear_slot === true;
    $("chat-inspect-summary").textContent = clearSupported
      ? "KV slots refreshed; clear action supported"
      : "KV slots refreshed; clear action not advertised by runtime";
  } catch (error) {
    showToast(error.message);
  }
}

async function clearKvSlot() {
  const model = $("chat-model").value;
  const target = $("chat-target").value || "auto";
  const slotId = Number($("chat-kv-slot-id").value || "");
  if (!model) return showToast("Select a model first.");
  if (!Number.isInteger(slotId) || slotId < 0) return showToast("Enter a valid slot id.");
  if (!confirmAction(`Clear KV slot ${slotId} for ${model}?`)) return;
  try {
    if (shouldDryRun()) {
      await writeAuditEvent({
        actor: "ui",
        event_type: "kv_clear_slot",
        dry_run: true,
        target: `${model}:${slotId}`,
        route: target,
        payload: { action: "clear" },
      });
      $("log-title").textContent = "dry-run kv clear";
      $("log-output").textContent = JSON.stringify(
        { method: "POST", path: `/chat/${model}/kv/slots/${slotId}`, body: { target, action: "clear" } },
        null,
        2
      );
      openLogModal();
      showToast("Dry run only: request not sent");
      return;
    }
    await writeAuditEvent({
      actor: "ui",
      event_type: "kv_clear_slot",
      dry_run: false,
      target: `${model}:${slotId}`,
      route: target,
      payload: { action: "clear" },
    });
    const payload = await api(`/chat/${encodeURIComponent(model)}/kv/slots/${slotId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target, action: "clear" }),
    });
    $("log-title").textContent = `kv slot cleared / ${model} / ${slotId}`;
    $("log-output").textContent = JSON.stringify(payload, null, 2);
    openLogModal();
    showToast(`Cleared KV slot ${slotId}`);
  } catch (error) {
    showToast(error.message);
  }
}

function formatCpu(cpu) {
  if (!cpu || typeof cpu.percent !== "number") return "-";
  return `${cpu.percent.toFixed(0)}%`;
}

function formatRam(ram) {
  if (!ram || typeof ram.percent !== "number") return "-";
  return `${ram.percent.toFixed(0)}% used`;
}

function formatVram(vram) {
  if (!Array.isArray(vram) || !vram.length) return "-";
  return vram
    .map((gpu) => `${gpu.memory_used_mb}/${gpu.memory_total_mb} MB`)
    .join(", ");
}

function formatGb(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return `${value.toFixed(2)} GB`;
}

function formatBytes(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return "unknown bytes";
  return `${value.toLocaleString()} bytes`;
}

function showToast(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => {
    toast.classList.remove("visible");
  }, 3600);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function shortPath(value) {
  const text = String(value);
  if (text.length <= 34) return text;
  return `...${text.slice(-31)}`;
}

function formatSliderValue(id, rawValue) {
  const value = Number(rawValue);
  if (["chat-top-p", "chat-min-p", "chat-repeat-penalty"].includes(id)) return value.toFixed(2);
  if (id === "chat-temperature") return value.toFixed(2);
  return String(Math.trunc(value));
}

function updateChatSliderValue(id) {
  const input = $(id);
  const output = $(`${id}-value`);
  if (!input || !output) return;
  output.textContent = formatSliderValue(id, input.value);
}

function refreshChatSliderValues() {
  ["chat-temperature", "chat-max-tokens", "chat-top-p", "chat-top-k", "chat-min-p", "chat-repeat-penalty", "chat-seed"].forEach(updateChatSliderValue);
}

document.querySelectorAll("[data-page-target]").forEach((button) => {
  button.addEventListener("click", () => {
    setActivePage(button.dataset.pageTarget);
    document.body.classList.remove("sidebar-open");
  });
});
$("refresh-button").addEventListener("click", refreshAll);
$("open-logs-button")?.addEventListener("click", openLogModal);
$("mobile-menu-button")?.addEventListener("click", () => {
  document.body.classList.toggle("sidebar-open");
});
$("open-chat-advanced")?.addEventListener("click", () => openDrawer("chat-advanced-drawer"));
document.querySelectorAll("[data-drawer-close]").forEach((element) => {
  element.addEventListener("click", () => closeDrawer(element.closest(".drawer")));
});
document.querySelectorAll("[data-modal-close]").forEach((element) => {
  element.addEventListener("click", () => closeModal(element.closest(".modal")));
});
document.querySelectorAll("dialog.modal").forEach((modal) => {
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal(modal);
  });
  modal.addEventListener("close", () => {
    if (modal.id === "logs-modal") stopLogStream();
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
  });
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.querySelectorAll(".drawer.open").forEach((drawer) => closeDrawer(drawer));
    document.querySelectorAll(".modal.open").forEach((modal) => closeModal(modal));
    document.body.classList.remove("sidebar-open");
  }
});
$("send-chat-button").addEventListener("click", sendChat);
$("clear-chat-button").addEventListener("click", clearChat);
$("chat-stop-button").addEventListener("click", stopChatGeneration);
$("chat-regenerate-button").addEventListener("click", regenerateLastResponse);
$("chat-inspect-button").addEventListener("click", inspectChatPrompt);
$("chat-capabilities-copy")?.addEventListener("click", () => void copyChatCapabilitiesJson());
$("chat-kv-refresh-button")?.addEventListener("click", () => void refreshKvSlots());
$("chat-kv-clear-button")?.addEventListener("click", () => void clearKvSlot());
$("chat-session-select")?.addEventListener("change", (event) => {
  state.selectedChatSessionId = event.target.value || "";
  persistActiveChatSessionId(state.selectedChatSessionId);
});
$("chat-session-save-button")?.addEventListener("click", () => void saveChatSession());
$("chat-session-save-as-new-button")?.addEventListener("click", () => void saveChatSession({ saveAsNew: true }));
$("chat-session-load-button")?.addEventListener("click", () => void loadChatSession());
$("chat-session-delete-button")?.addEventListener("click", () => void deleteChatSession());
$("embeddings-run-button")?.addEventListener("click", () => void runEmbeddings());
$("embeddings-export-json")?.addEventListener("click", exportEmbeddingsJson);
$("embeddings-export-csv")?.addEventListener("click", exportEmbeddingsCsv);
$("embeddings-similarity-button")?.addEventListener("click", computeSimilarityTable);
$("embeddings-neighbors-button")?.addEventListener("click", computeNearestNeighbors);
$("embeddings-cluster-button")?.addEventListener("click", runQuickClusters);
$("advisor-run-button")?.addEventListener("click", recommendQuantization);
$("gguf-detail-add-button")?.addEventListener("click", () => void addSelectedGgufModel());
$("gguf-detail-remove-button")?.addEventListener("click", () => void removeSelectedGgufModel());
$("gguf-detail-delete-button")?.addEventListener("click", () => void deleteSelectedGguf());
$("chat-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendChat();
  }
});
$("chat-model").addEventListener("change", () => {
  void refreshChatCapabilities();
});
$("chat-target").addEventListener("change", () => {
  void refreshKvCapabilities();
});
$("chat-preset").addEventListener("change", applyChatPreset);
  $("chat-structured-mode").addEventListener("change", applyStructuredModeUI);
  $("chat-json-schema").addEventListener("input", applyStructuredModeUI);
  $("chat-grammar").addEventListener("input", applyStructuredModeUI);
  restoreChatPreset();
  refreshChatSliderValues();
  applyStructuredModeUI();
["chat-temperature", "chat-max-tokens", "chat-top-p", "chat-top-k", "chat-min-p", "chat-repeat-penalty", "chat-seed", "chat-stop"].forEach((id) => {
  $(id).addEventListener("input", () => {
    updateChatSliderValue(id);
    renderChatDefaultsDiff();
  });
});
$("controller-export-button")?.addEventListener("click", async () => {
  try {
    if (!confirmAction("Confirm controller archive export?")) return;
    if (shouldDryRun()) {
      await writeAuditEvent({
        actor: "ui",
        event_type: "controller_archive_export",
        dry_run: true,
        target: "controller",
        route: "controller",
        payload: { path: "/controller/archive/export" },
      });
      $("log-title").textContent = "dry-run controller export";
      $("log-output").textContent = JSON.stringify({ method: "POST", path: "/controller/archive/export" }, null, 2);
      openLogModal();
      showToast("Dry run only: request not sent");
      return;
    }
    await writeAuditEvent({
      actor: "ui",
      event_type: "controller_archive_export",
      dry_run: false,
      target: "controller",
      route: "controller",
      payload: { path: "/controller/archive/export" },
    });
    const result = await api("/controller/archive/export", { method: "POST" });
    showToast(`Archive export complete: ${result.jobs_exported} jobs`);
    await refreshAll();
  } catch (error) {
    showToast(error.message);
  }
});
["audit-filter-type", "audit-filter-target", "audit-filter-dry-run", "audit-filter-from", "audit-filter-to", "audit-limit"].forEach((id) => {
  $(id)?.addEventListener("input", () => {
    void refreshAuditEvents();
  });
});
$("audit-refresh-button")?.addEventListener("click", () => void refreshAuditEvents());
$("audit-my-actions-button")?.addEventListener("click", applyMyActionsFilter);
["nodes-filter-name", "nodes-filter-status", "nodes-filter-registration"].forEach((id) => {
  $(id)?.addEventListener(id === "nodes-filter-name" ? "input" : "change", renderNodesPage);
});
$("nodes-refresh-button")?.addEventListener("click", () => void refreshNodesPageData());
$("node-edit-save-button")?.addEventListener("click", () => void saveNodeEdit().catch((e) => showToast(e.message)));
$("keys-create-button")?.addEventListener("click", () => void createAuthKey().catch((e) => showToast(e.message)));
$("keys-refresh-button")?.addEventListener("click", () => void refreshAuthKeys());
$("download-refresh-button")?.addEventListener("click", () => void refreshAll());
["settings-log-dir", "settings-mode", "settings-controller-url", "settings-controller-api-key", "settings-registration-key", "settings-agent-api-key", "settings-agent-name", "settings-agent-url"].forEach((id) => {
  $(id)?.addEventListener("input", renderSettingsConfig);
  $(id)?.addEventListener("change", renderSettingsConfig);
});
$("settings-build-config")?.addEventListener("click", renderSettingsConfig);
$("settings-generate-key")?.addEventListener("click", async () => {
  try {
    await generateSettingsApiKeys();
    showToast("Generated API key(s)");
  } catch (error) {
    showToast(error.message);
  }
});
$("settings-apply-generated-key")?.addEventListener("click", async () => {
  try {
    const payload = await generateSettingsApiKeys();
    const key = payload?.keys?.[0];
    if (!key) return showToast("No keys returned");
    const target = $("settings-key-apply-target")?.value || "controller";
    if (target === "registration") $("settings-registration-key").value = key;
    else if (target === "agent") $("settings-agent-api-key").value = key;
    else $("settings-controller-api-key").value = key;
    renderSettingsConfig();
    showToast("Applied generated key");
  } catch (error) {
    showToast(error.message);
  }
});
$("settings-copy-config")?.addEventListener("click", async () => {
  const text = $("settings-config-output")?.textContent || "";
  if (!text.trim()) return showToast("Generate config first.");
  try {
    await navigator.clipboard.writeText(text);
    showToast("config.yaml copied");
  } catch (_error) {
    showToast("Clipboard copy failed");
  }
});
$("settings-download-config")?.addEventListener("click", () => {
  const text = $("settings-config-output")?.textContent || "";
  if (!text.trim()) return showToast("Generate config first.");
  downloadText("config.yaml", text, "application/x-yaml");
});
$("settings-copy-exports")?.addEventListener("click", async () => {
  const text = $("settings-exports-output")?.textContent || "";
  if (!text.trim()) return showToast("Generate config first.");
  try {
    await navigator.clipboard.writeText(text);
    showToast("Env exports copied");
  } catch (_error) {
    showToast("Clipboard copy failed");
  }
});
$("settings-download-exports")?.addEventListener("click", () => {
  const text = $("settings-exports-output")?.textContent || "";
  if (!text.trim()) return showToast("Generate config first.");
  downloadText("llama-manager-env.sh", text, "text/x-shellscript");
});
document.querySelectorAll("[data-settings-tab-target]").forEach((button) => {
  button.addEventListener("click", () => {
    const target = button.getAttribute("data-settings-tab-target");
    if (!target) return;
    document.querySelectorAll("[data-settings-tab-target]").forEach((tab) => {
      const active = tab.getAttribute("data-settings-tab-target") === target;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    document.querySelectorAll("[data-settings-tab-panel]").forEach((panel) => {
      const active = panel.getAttribute("data-settings-tab-panel") === target;
      panel.classList.toggle("active", active);
      panel.hidden = !active;
    });
  });
});
document.querySelectorAll("[data-settings-pane-target]").forEach((button) => {
  button.addEventListener("click", () => {
    const target = button.getAttribute("data-settings-pane-target");
    if (!target) return;
    document.querySelectorAll("[data-settings-pane-target]").forEach((tab) => {
      const active = tab.getAttribute("data-settings-pane-target") === target;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    document.querySelectorAll("[data-settings-pane]").forEach((panel) => {
      const active = panel.getAttribute("data-settings-pane") === target;
      panel.classList.toggle("active", active);
      panel.hidden = !active;
    });
  });
});

function onDownloadStartClick() {
  const repoId = ($("download-repo-id")?.value || "").trim();
  if (!repoId) {
    showToast("Enter owner/model");
    return;
  }
  void runDownloadAction({ downloadId: "", repoId, action: "start" }).catch((error) => {
    showToast(error?.message || "Download request failed");
  });
}

$("download-form")?.addEventListener("submit", (event) => {
  event.preventDefault();
  onDownloadStartClick();
});
window.addEventListener("hashchange", () => setActivePage(window.location.hash.slice(1)));
setActivePage(window.location.hash.slice(1) || "dashboard");
$("auth-login-button")?.addEventListener("click", () => void loginUi().then(() => refreshAll()).catch((e) => showToast(e.message)));
$("auth-logout-button")?.addEventListener("click", () => void logoutUi());
hydrateIcons();
applyChatPreset();
renderChatDefaultsDiff();
renderSettingsConfig();
bootstrapAuth().then(() => refreshAll());


function eventRowClass(eventType) {
  const t = String(eventType || "").toLowerCase();
  if (t.includes("assigned")) return "chip-assigned";
  if (t.includes("progress")) return "chip-progress";
  if (t.includes("complete")) return "chip-complete";
  if (t.includes("fail") || t.includes("error")) return "chip-fail";
  if (t.includes("retry")) return "chip-retry";
  return "";
}
