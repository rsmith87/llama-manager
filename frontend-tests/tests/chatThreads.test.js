import { describe, expect, it } from "vitest";
import {
  buildThreadMetadata,
  threadEventsToChatMessages,
} from "../../llama_manager/ui/chat_threads.js";

describe("thread event transcript mapping", () => {
  it("renders public user and assistant events with route metadata", () => {
    const messages = threadEventsToChatMessages([
      {
        event_type: "user_message",
        role: "user",
        content: { text: "hello" },
        public: true,
      },
      {
        event_type: "assistant_message",
        role: "assistant",
        content: { text: "hi" },
        public: true,
        route: { node: "linux-2080ti", model: "qwen", reason: "request_type" },
        agent_node: "linux-2080ti",
        model: "qwen",
      },
    ]);

    expect(messages).toEqual([
      { role: "user", content: "hello", threadEventType: "user_message" },
      {
        role: "assistant",
        content: "hi",
        threadEventType: "assistant_message",
        routeMeta: {
          model: "qwen",
          target: "node:linux-2080ti",
          resolved: "linux-2080ti",
          reason: "request_type",
        },
      },
    ]);
  });

  it("renders internal routing decisions as internal transcript rows", () => {
    const [message] = threadEventsToChatMessages([
      {
        event_type: "routing_decision",
        public: false,
        content: { candidates: [{ node: "mac" }, { node: "linux" }] },
        route: { node: "linux", model: "qwen", reason: "request_type" },
        agent_node: "linux",
        model: "qwen",
      },
    ]);

    expect(message.role).toBe("internal");
    expect(message.content).toBe("routing_decision node=linux model=qwen reason=request_type candidates=2");
    expect(message.routeMeta.resolved).toBe("linux");
  });
});

describe("thread metadata payloads", () => {
  it("normalizes empty optional fields to null", () => {
    expect(buildThreadMetadata({ app: " codex ", purpose: "", priority: "high", requestType: "coding" })).toEqual({
      app: "codex",
      purpose: null,
      priority: "high",
      request_type: "coding",
    });
  });
});
