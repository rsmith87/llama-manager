export function buildChatSessionSavePayload({
  name,
  model,
  target = "auto",
  messages = [],
  requestDefaults = {},
  selectedSessionId = "",
  saveAsNew = false,
} = {}) {
  const payload = {
    name,
    model,
    target,
    messages,
    request_defaults: requestDefaults,
  };
  const normalizedSessionId = typeof selectedSessionId === "string" ? selectedSessionId.trim() : "";
  if (!saveAsNew && normalizedSessionId) {
    payload.id = normalizedSessionId;
  }
  return payload;
}

export function nextSelectedChatSessionId({ savedSessionId, saveAsNew = false } = {}) {
  if (typeof savedSessionId !== "string") {
    return "";
  }
  const normalizedSessionId = savedSessionId.trim();
  if (!normalizedSessionId) {
    return "";
  }
  return normalizedSessionId;
}
