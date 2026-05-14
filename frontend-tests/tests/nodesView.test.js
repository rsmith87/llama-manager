import { describe, expect, it } from "vitest";
import {
  filterNodes,
  mergeNodeInventory,
  nodeSummary,
  sortModelsForDisplay,
  suggestedGgufModelName,
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

  it("sorts favorite models first, then by name", () => {
    expect(
      sortModelsForDisplay([
        { name: "qwen", favorite: false },
        { name: "mistral", favorite: true },
        { name: "gemma", favorite: true },
      ]).map((model) => model.name),
    ).toEqual(["gemma", "mistral", "qwen"]);
  });
});
