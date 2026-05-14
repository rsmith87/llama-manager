from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, IO

from llama_manager.core.config import AppConfig, ModelConfig, save_config
from llama_manager.providers.llama_cpp import build_llama_server_command


PopenFactory = Callable[..., subprocess.Popen]


@dataclass
class ModelStatus:
    name: str
    running: bool
    pid: int | None
    port: int
    model_path: str
    log_path: str
    favorite: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ProcessManager:
    def __init__(self, config: AppConfig, popen: PopenFactory = subprocess.Popen):
        self.config = config
        self._popen = popen
        self._processes: dict[str, subprocess.Popen] = {}
        self._log_handles: dict[str, IO[bytes]] = {}
        self.config.log_dir.mkdir(parents=True, exist_ok=True)

    def list_statuses(self) -> list[dict[str, object]]:
        return [
            self.status(name).to_dict()
            for name in sorted(
                self.config.models,
                key=lambda item: (not self.config.models[item].favorite, item.lower()),
            )
        ]

    def status(self, name: str) -> ModelStatus:
        model = self._get_model(name)
        process = self._processes.get(name)
        running = process is not None and process.poll() is None
        if process is not None and not running:
            self._processes.pop(name, None)
            self._close_log(name)
            process = None
        return ModelStatus(
            name=name,
            running=running,
            pid=process.pid if running and process is not None else None,
            port=model.port,
            model_path=model.path,
            log_path=str(self._log_path(name)),
            favorite=model.favorite,
        )

    def set_favorite(self, name: str, favorite: bool) -> ModelStatus:
        model = self._get_model(name)
        model.favorite = favorite
        if self.config.config_source not in {"(defaults)", "(in-memory)"}:
            save_config(self.config)
        return self.status(name)

    def start(self, name: str) -> ModelStatus:
        current = self.status(name)
        if current.running:
            return current

        model = self._get_model(name)
        log_path = self._log_path(name)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("ab")
        command = build_llama_server_command(self.config.llama_server_bin, model)
        process = self._popen(command, stdout=log_handle, stderr=log_handle, cwd=None)
        self._processes[name] = process
        self._log_handles[name] = log_handle
        return self.status(name)

    def stop(self, name: str) -> ModelStatus:
        self._get_model(name)
        process = self._processes.get(name)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        self._processes.pop(name, None)
        self._close_log(name)
        return self.status(name)

    def restart(self, name: str) -> ModelStatus:
        self.stop(name)
        return self.start(name)

    def tail_logs(self, name: str, lines: int = 200) -> str:
        self._get_model(name)
        log_path = self._log_path(name)
        if not log_path.exists():
            return ""
        requested = max(1, min(lines, 2000))
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            return "".join(handle.readlines()[-requested:])

    def _get_model(self, name: str) -> ModelConfig:
        try:
            return self.config.models[name]
        except KeyError as exc:
            raise KeyError(f"Unknown model: {name}") from exc

    def _log_path(self, name: str) -> Path:
        return self.config.log_dir / f"{name}.log"

    def _close_log(self, name: str) -> None:
        handle = self._log_handles.pop(name, None)
        if handle is not None and not handle.closed:
            handle.close()
