export function asNumber(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  return value;
}

export function applyTelemetryFromChunk(chunk, pendingMessage) {
  const usage = chunk?.usage || {};
  const timings = chunk?.timings || {};
  const promptTokens = asNumber(usage.prompt_tokens);
  const completionTokens = asNumber(usage.completion_tokens);
  const promptMs = asNumber(timings.prompt_ms);
  const predictedMs = asNumber(timings.predicted_ms);
  const predictedN = asNumber(timings.predicted_n);
  const completionMs = predictedMs ?? asNumber(usage.completion_time_ms);
  const completionN = predictedN ?? completionTokens;
  const tokensPerSecond = completionMs && completionN && completionMs > 0
    ? (completionN * 1000) / completionMs
    : null;

  pendingMessage.telemetry = {
    ...(pendingMessage.telemetry || {}),
    ...(promptTokens != null ? { promptTokens } : {}),
    ...(completionTokens != null ? { completionTokens } : {}),
    ...(promptMs != null ? { promptMs } : {}),
    ...(completionMs != null ? { completionMs } : {}),
    ...(tokensPerSecond != null ? { tokensPerSecond } : {}),
  };
}

export function finalizeTelemetry(pendingMessage, nowMs) {
  const now = typeof nowMs === "number" ? nowMs : performance.now();
  const start = pendingMessage.startedAtMs || now;
  const totalMs = now - start;
  const hasOutput = Boolean(pendingMessage.content || pendingMessage.reasoningContent);
  const ttftMs = pendingMessage.firstTokenAtMs
    ? pendingMessage.firstTokenAtMs - start
    : hasOutput
      ? totalMs
      : null;

  pendingMessage.telemetry = {
    ...(pendingMessage.telemetry || {}),
    ...(ttftMs != null ? { ttftMs } : {}),
    totalMs,
  };
}

export function parseSseEvents(bufferText) {
  const events = bufferText.split("\n\n");
  return {
    events: events.slice(0, -1),
    remainder: events.at(-1) || "",
  };
}

export function parseSseDataLines(eventText) {
  return eventText
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim());
}
