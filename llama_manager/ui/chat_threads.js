export function threadEventToChatMessage(event) {
  const content = event?.content || {};
  const text = typeof content.text === "string" ? content.text : "";
  const route = event?.route || {};
  if (event?.event_type === "user_message") {
    return {
      role: "user",
      content: text,
      threadEventType: event.event_type,
    };
  }
  if (event?.event_type === "assistant_message") {
    return {
      role: "assistant",
      content: text,
      threadEventType: event.event_type,
      routeMeta: {
        model: event.model || route.model || "",
        target: event.agent_node ? `node:${event.agent_node}` : "",
        resolved: event.agent_node || route.node || "",
        reason: route.reason || "",
      },
    };
  }
  if (event?.event_type === "routing_decision") {
    return {
      role: "internal",
      content: formatRoutingDecision(event),
      threadEventType: event.event_type,
      routeMeta: {
        model: event.model || route.model || "",
        target: event.agent_node ? `node:${event.agent_node}` : "",
        resolved: event.agent_node || route.node || "",
        reason: route.reason || "",
      },
    };
  }
  if (event?.event_type === "error") {
    return {
      role: "error",
      content: event.error_detail || text || "Thread request failed",
      threadEventType: event.event_type,
    };
  }
  return {
    role: event?.public === false ? "internal" : event?.role || "assistant",
    content: text || JSON.stringify(content, null, 2),
    threadEventType: event?.event_type || "event",
  };
}

export function threadEventsToChatMessages(events) {
  return (events || []).map(threadEventToChatMessage);
}

export function buildThreadMetadata({ app, purpose, priority, requestType }) {
  return {
    app: normalizeOptional(app),
    purpose: normalizeOptional(purpose),
    priority: priority || "medium",
    request_type: requestType || "general",
  };
}

function normalizeOptional(value) {
  const trimmed = String(value || "").trim();
  return trimmed || null;
}

function formatRoutingDecision(event) {
  const route = event.route || {};
  const content = event.content || {};
  const parts = [
    route.node || content.node ? `node=${route.node || content.node}` : null,
    route.model || content.model ? `model=${route.model || content.model}` : null,
    route.reason || content.reason ? `reason=${route.reason || content.reason}` : null,
    Array.isArray(content.candidates) ? `candidates=${content.candidates.length}` : null,
  ].filter(Boolean);
  return parts.length ? `routing_decision ${parts.join(" ")}` : "routing_decision";
}
