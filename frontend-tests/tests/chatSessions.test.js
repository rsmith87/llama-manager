import { describe, expect, it } from "vitest";
import {
  CHAT_SESSION_MAX_AGE_MS,
  buildChatSessionSavePayload,
  chooseChatSessionToResume,
  isChatSessionReusable,
  nextSelectedChatSessionId,
} from "../../llama_manager/ui/chat_sessions.js";

describe("chat session save payload", () => {
  it("reuses the selected session id for a normal save", () => {
    const payload = buildChatSessionSavePayload({
      name: "Obliterated-session-5-12-2026",
      model: "qwen",
      target: "auto",
      messages: [{ role: "user", content: "hello" }],
      requestDefaults: { temperature: 0.2 },
      selectedSessionId: "session-123",
    });

    expect(payload).toEqual({
      id: "session-123",
      name: "Obliterated-session-5-12-2026",
      model: "qwen",
      target: "auto",
      messages: [{ role: "user", content: "hello" }],
      request_defaults: { temperature: 0.2 },
    });
  });

  it("omits the session id when saving as new", () => {
    const payload = buildChatSessionSavePayload({
      name: "Obliterated-session-5-12-2026",
      model: "qwen",
      target: "auto",
      messages: [{ role: "user", content: "hello" }],
      requestDefaults: { temperature: 0.2 },
      selectedSessionId: "session-123",
      saveAsNew: true,
    });

    expect(payload).toEqual({
      name: "Obliterated-session-5-12-2026",
      model: "qwen",
      target: "auto",
      messages: [{ role: "user", content: "hello" }],
      request_defaults: { temperature: 0.2 },
    });
  });
});

describe("chat session selection after save", () => {
  it("tracks the saved session id after overwrite", () => {
    expect(nextSelectedChatSessionId({ savedSessionId: "session-123" })).toBe("session-123");
  });

  it("tracks the new session id after save-as-new", () => {
    expect(nextSelectedChatSessionId({ savedSessionId: "session-456", saveAsNew: true })).toBe("session-456");
  });
});

describe("chat session resume policy", () => {
  const nowMs = Date.parse("2026-05-13T12:00:00Z");

  it("treats sessions newer than 24 hours as reusable", () => {
    expect(
      isChatSessionReusable(
        { updated_at: new Date(nowMs - CHAT_SESSION_MAX_AGE_MS + 1000).toISOString() },
        nowMs
      )
    ).toBe(true);
  });

  it("treats sessions at or beyond 24 hours as expired", () => {
    expect(
      isChatSessionReusable(
        { updated_at: new Date(nowMs - CHAT_SESSION_MAX_AGE_MS).toISOString() },
        nowMs
      )
    ).toBe(false);
  });

  it("prefers the locally active session when it is still reusable", () => {
    const sessions = [
      { id: "older", updated_at: "2026-05-13T08:00:00Z" },
      { id: "preferred", updated_at: "2026-05-13T10:00:00Z" },
    ];

    expect(
      chooseChatSessionToResume({ sessions, preferredSessionId: "preferred", nowMs })
    ).toBe("preferred");
  });

  it("falls back to the most recent reusable session when the preferred one expired", () => {
    const sessions = [
      { id: "newest", updated_at: "2026-05-13T11:00:00Z" },
      { id: "expired", updated_at: "2026-05-12T11:00:00Z" },
    ];

    expect(
      chooseChatSessionToResume({ sessions, preferredSessionId: "expired", nowMs })
    ).toBe("newest");
  });

  it("returns empty when no reusable session exists", () => {
    const sessions = [{ id: "expired", updated_at: "2026-05-12T11:00:00Z" }];

    expect(
      chooseChatSessionToResume({ sessions, preferredSessionId: "expired", nowMs })
    ).toBe("");
  });
});
