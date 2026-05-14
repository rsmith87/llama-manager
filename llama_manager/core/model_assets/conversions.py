from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, IO

from llama_manager.core.config import AppConfig


PopenFactory = Callable[..., subprocess.Popen]


class ConversionManager:
    def __init__(self, config: AppConfig, popen: PopenFactory = subprocess.Popen):
        self.config = config
        self._popen = popen
        self._processes: dict[str, subprocess.Popen] = {}
        self._log_handles: dict[str, IO[bytes]] = {}
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def list_models(self) -> list[dict[str, object]]:
        models = []
        for root in self.config.model_roots:
            if not root.exists():
                continue
            for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
                if not path.is_dir() or path.name.startswith("."):
                    continue
                status = self._status_for_path(path.name, path)
                if status["convertible"] or status["gguf_exists"]:
                    models.append(status)
        return models

    def status(self, name: str) -> dict[str, object]:
        model_path = self._model_path(name)
        if not model_path.exists() or not model_path.is_dir():
            raise KeyError(f"Unknown HF model: {name}")
        return self._status_for_path(name, model_path)

    def start(self, name: str) -> dict[str, object]:
        current = self.status(name)
        if current["running"]:
            return current
        if not current["convertible"]:
            raise ValueError(f"HF model is not convertible: {name}")

        log_path = self._log_path(name)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("ab")
        process = self._popen(
            self._command(name),
            stdout=log_handle,
            stderr=log_handle,
            cwd=None,
        )
        self._processes[name] = process
        self._log_handles[name] = log_handle
        return self.status(name)

    def tail_logs(self, name: str, lines: int = 200) -> str:
        self.status(name)
        log_path = self._log_path(name)
        if not log_path.exists():
            return ""
        requested = max(1, min(lines, 2000))
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            return "".join(handle.readlines()[-requested:])

    def _status_for_path(self, name: str, model_path: Path) -> dict[str, object]:
        process = self._processes.get(name)
        returncode = process.poll() if process is not None else None
        running = process is not None and returncode is None
        if process is not None and not running:
            self._close_log(name)

        output_path = self._output_path(name, model_path)
        gguf_files = self._gguf_files(model_path)
        return {
            "name": name,
            "path": str(model_path),
            "convertible": self._is_convertible(model_path),
            "output_path": str(output_path),
            "gguf_exists": bool(gguf_files),
            "gguf_files": [str(path) for path in gguf_files],
            "converter_path": str(self._converter_path),
            "python_bin": self.config.python_bin,
            "running": running,
            "pid": process.pid if running else None,
            "returncode": returncode,
            "log_path": str(self._log_path(name)),
        }

    def _is_convertible(self, model_path: Path) -> bool:
        has_config = (model_path / "config.json").exists()
        has_weights = any(model_path.glob("*.safetensors")) or any(model_path.glob("*.bin"))
        return has_config and has_weights and self._converter_path.exists()

    def _command(self, name: str) -> list[str]:
        model_path = self._model_path(name)
        return [
            self.config.python_bin,
            str(self._converter_path),
            str(model_path),
            "--outfile",
            str(self._output_path(name, model_path)),
        ]

    def _model_path(self, name: str) -> Path:
        if "/" in name or "\\" in name or name in {"", ".", ".."}:
            raise KeyError(f"Unknown HF model: {name}")
        for root in self.config.model_roots:
            candidate = root / name
            if candidate.exists() and candidate.is_dir():
                return candidate
        first_root = self.config.model_roots[0] if self.config.model_roots else Path(".")
        return first_root / name

    def _output_path(self, name: str, model_path: Path) -> Path:
        return model_path / f"{name}.gguf"

    def _gguf_files(self, model_path: Path) -> list[Path]:
        return sorted(model_path.glob("*.gguf"), key=lambda path: path.name.lower())

    @property
    def _converter_path(self) -> Path:
        return self.config.llama_cpp_dir / "convert_hf_to_gguf.py"

    @property
    def _log_dir(self) -> Path:
        return self.config.log_dir / "conversions"

    def _log_path(self, name: str) -> Path:
        return self._log_dir / f"{name}.log"

    def _close_log(self, name: str) -> None:
        handle = self._log_handles.pop(name, None)
        if handle is not None and not handle.closed:
            handle.close()
