from __future__ import annotations

from llama_manager.core.config import ModelConfig


def build_llama_server_command(binary: str, model: ModelConfig) -> list[str]:
    command = [
        binary,
        "--model",
        model.path,
        "--host",
        model.host,
        "--port",
        str(model.port),
        "--ctx-size",
        str(model.ctx),
        "--n-gpu-layers",
        str(model.gpu_layers),
    ]
    if model.reasoning is not None:
        command.extend(["--reasoning", model.reasoning])
    if model.reasoning_budget is not None:
        command.extend(["--reasoning-budget", str(model.reasoning_budget)])
    if model.mmproj:
        command.extend(["--mmproj", model.mmproj])
    command.extend(model.extra_args)
    return command
