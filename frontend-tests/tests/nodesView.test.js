import { describe, expect, it } from "vitest";
import {
  filterNodes,
  mergeNodeInventory,
  nodeSummary,
  nodeEditFormDefaults,
  nodeEditMarkup,
  PROMPT_TEMPLATE_OPTIONS,
  sortModelsForDisplay,
  suggestedGgufModelName,
  suggestedPromptTemplate,
} from "../../llama_manager/ui/nodes_view.js";

const nodes = [
  {
    name: "mac-agent",
    url: "http://mac:9000",
    reachable: true,
    registration: "static",
    agent_config_source: "/etc/mac.yaml",
    models: [{ name: "qwen" }, { name: "gemma" }],
  },
  {
    name: "win-agent",
    url: "http://win:9000",
    reachable: false,
    registration: "dynamic",
    controller_config_source: "controller.yaml",
    models: [],
  },
];

describe("nodes view helpers", () => {
  it("filters nodes by text, status, and registration", () => {
    expect(filterNodes(nodes, { query: "mac", status: "reachable", registration: "static" })).toEqual([nodes[0]]);
    expect(filterNodes(nodes, { status: "offline" })).toEqual([nodes[1]]);
    expect(filterNodes(nodes, { query: "controller" })).toEqual([nodes[1]]);
  });

  it("summarizes reachable nodes and model count", () => {
    expect(nodeSummary(nodes)).toEqual({ reachable: 1, total: 2, models: 2 });
  });

  it("merges configured inventory with aggregate model status", () => {
    expect(
      mergeNodeInventory(
        [
          {
            name: "win-agent",
            url: "http://win:9000",
            registration: "static",
          },
          {
            name: "mac-agent",
            url: "http://mac:9000",
            registration: "dynamic",
          },
        ],
        [
          {
            name: "win-agent",
            reachable: true,
            models: [{ name: "qwen" }],
            models_source: "worker",
          },
        ],
      ),
    ).toEqual([
      {
        name: "mac-agent",
        url: "http://mac:9000",
        registration: "dynamic",
        reachable: false,
        models: [],
      },
      {
        name: "win-agent",
        url: "http://win:9000",
        registration: "static",
        reachable: true,
        models: [{ name: "qwen" }],
        models_source: "worker",
      },
    ]);
  });

  it("defaults GGUF model names from the file stem before the directory", () => {
    expect(
      suggestedGgufModelName({
        name: "qwen3-q4-k-m",
        model_dir: "qwen3",
      }),
    ).toBe("qwen3-q4-k-m");
    expect(suggestedGgufModelName({ model_dir: "qwen3" })).toBe("qwen3");
  });

  it("infers GGUF prompt templates from model names", () => {
    expect(suggestedPromptTemplate({ name: "Meta-Llama-3.1-8B-Instruct" })).toBe("llama3");
    expect(suggestedPromptTemplate({ model_dir: "gemma-3-4b-it" })).toBe("gemma");
    expect(suggestedPromptTemplate({ filename: "gpt-oss-20b-Q4_K_M.gguf" })).toBe("gpt-oss");
    expect(suggestedPromptTemplate({ name: "Qwen2.5-Coder-Instruct" })).toBe("qwen");
    expect(suggestedPromptTemplate({ name: "mistral-7b" })).toBe("");
  });

  it("lists the backend default prompt template aliases for GGUF imports", () => {
    expect(PROMPT_TEMPLATE_OPTIONS.map((option) => option.value)).toEqual([
      "",
      "llama3",
      "llama-3",
      "chatml",
      "qwen",
      "gemma",
      "gpt-oss",
      "gptoss",
    ]);
  });

  it("sorts favorite models first, then by name", () => {
    expect(
      sortModelsForDisplay([
        { name: "qwen", favorite: false },
        { name: "mistral", favorite: true },
        { name: "gemma", favorite: true },
      ]).map((model) => model.name),
    ).toEqual(["gemma", "mistral", "qwen"]);
  });

  it("builds node edit defaults and only shows edit actions for full cards", () => {
    expect(nodeEditFormDefaults({ name: "win", url: "http://win:9000", verify_tls: false })).toEqual({
      name: "win",
      url: "http://win:9000",
      api_key: "",
      verify_tls: false,
    });
    expect(nodeEditFormDefaults({ name: "mac", url: "http://mac:9000" }).verify_tls).toBe(true);
    expect(nodeEditMarkup(nodes[0], { compact: false })).toContain('data-edit-node="mac-agent"');
    expect(nodeEditMarkup(nodes[0], { compact: false })).toContain("Edit Node");
    expect(nodeEditMarkup(nodes[0], { compact: true })).toBe("");
  });
});
