from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from llama_manager.core.config import AppConfig, ModelConfig, save_config


ReasoningMode = Literal["on", "off", "auto"]


class GgufLibrary:
    def __init__(self, config: AppConfig):
        self.config = config

    def list_files(self, recent_transfers: list[dict[str, object]] | None = None) -> list[dict[str, object]]:
        received_by_path = self._received_by_path(recent_transfers or [])
        files = []
        for path in self._gguf_paths():
            files.append(self._file_payload(path, received_by_path.get(str(path))))
        return files

    def add_model(
        self,
        file_id: str,
        name: str,
        port: int,
        ctx: int,
        gpu_layers: int,
        host: str,
        reasoning: ReasoningMode | None = None,
        reasoning_budget: int | None = None,
        prompt_template: str | None = None,
        favorite: bool | None = False
    ) -> dict[str, object]:
        path = self._path_for_id(file_id)
        model_name = name.strip()
        if not model_name:
            raise ValueError("Model name is required")
        if model_name in self.config.models:
            raise ValueError(f"Model already exists: {model_name}")

        self.config.models[model_name] = ModelConfig(
            path=str(path),
            port=port,
            ctx=ctx,
            gpu_layers=gpu_layers,
            host=host,
            reasoning=reasoning,
            reasoning_budget=reasoning_budget,
            prompt_template=prompt_template,
            favorite=favorite
        )
        if self.config.config_source not in {"(defaults)", "(in-memory)"}:
            save_config(self.config)
        model = self.config.models[model_name]
        return {
            "name": model_name,
            "path": model.path,
            "port": model.port,
            "ctx": model.ctx,
            "gpu_layers": model.gpu_layers,
            "host": model.host,
            "reasoning": model.reasoning,
            "reasoning_budget": model.reasoning_budget,
            "prompt_template": model.prompt_template,
            "favorite": model.favorite,
        }

    def remove_model(self, name: str) -> dict[str, object]:
        model_name = name.strip()
        if not model_name:
            raise ValueError("Model name is required")
        if model_name not in self.config.models:
            raise KeyError(f"Unknown model: {model_name}")
        removed = self.config.models.pop(model_name)
        if self.config.config_source not in {"(defaults)", "(in-memory)"}:
            save_config(self.config)
        return {"removed": True, "name": model_name, "path": removed.path}

    def delete_file(self, file_id: str) -> dict[str, object]:
        path = self._path_for_id(file_id)
        registered_names = self._registered_names(path)

        path.unlink()
        for name in registered_names:
            self.config.models.pop(name, None)
        if registered_names and self.config.config_source not in {"(defaults)", "(in-memory)"}:
            save_config(self.config)

        return {
            "deleted": True,
            "id": file_id,
            "filename": path.name,
            "path": str(path),
            "unregistered_models": registered_names,
        }

    def file_id(self, path: Path) -> str:
        resolved = str(path)
        return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]

    def _path_for_id(self, file_id: str) -> Path:
        for path in self._gguf_paths():
            if self.file_id(path) == file_id:
                return path
        raise KeyError(f"Unknown GGUF file id: {file_id}")

    def _gguf_paths(self) -> list[Path]:
        paths = []
        for root in self.config.model_roots:
            if root.exists():
                paths.extend(root.glob("*.gguf"))
                paths.extend(root.glob("*/*.gguf"))
        return sorted(paths, key=lambda item: str(item).lower())

    def _file_payload(self, path: Path, received: dict[str, object] | None = None) -> dict[str, object]:
        registered_as = self._registered_name(path)
        size_bytes = path.stat().st_size
        received_payload = received or {}
        return {
            "id": self.file_id(path),
            "name": path.stem,
            "filename": path.name,
            "model_dir": path.parent.name,
            "path": str(path),
            "size_bytes": size_bytes,
            "size_gb": round(size_bytes / (1024**3), 2),
            "registered": registered_as is not None,
            "registered_as": registered_as,
            "recently_received": bool(received_payload),
            "received_from_node": received_payload.get("source_node"),
            "received_transfer_id": received_payload.get("id"),
            "received_at": received_payload.get("completed_at"),
        }

    def _registered_name(self, path: Path) -> str | None:
        names = self._registered_names(path)
        return names[0] if names else None

    def _registered_names(self, path: Path) -> list[str]:
        target = str(path)
        names = []
        for name, model in self.config.models.items():
            if model.path == target:
                names.append(name)
        return names

    def _received_by_path(self, transfers: list[dict[str, object]]) -> dict[str, dict[str, object]]:
        result = {}
        for transfer in transfers:
            copied = transfer.get("copied", [])
            skipped = transfer.get("skipped", [])
            items = []
            if isinstance(copied, list):
                items.extend(copied)
            if isinstance(skipped, list):
                items.extend(skipped)
            for item in items:
                if isinstance(item, dict) and item.get("path"):
                    result[str(item["path"])] = transfer
        return result
