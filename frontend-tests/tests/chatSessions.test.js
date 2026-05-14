import { describe, expect, it } from "vitest";
import {
  buildChatSessionSavePayload,
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
