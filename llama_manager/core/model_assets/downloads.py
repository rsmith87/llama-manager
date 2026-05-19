from __future__ import annotations

import re
import subprocess
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, IO

from llama_manager.core.config import AppConfig
from llama_manager.core.persistence.model_download_store_orm import ModelDownloadStoreOrm


PopenFactory = Callable[..., subprocess.Popen]
REPO_PATTERN = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
GGUF_QUANT_PATTERN = re.compile(
    r"(?:^|[-_.])(MXFP[0-9](?:_[A-Z0-9]+)*|IQ[0-9](?:_[A-Z0-9]+)+|Q[0-9](?:_[A-Z0-9]+)+|F16|BF16|F32)(?:[-_.]|$)",
    re.IGNORECASE,
)


class DownloadManager:
    def __init__(
        self,
        config: AppConfig,
        store: ModelDownloadStoreOrm,
        popen: PopenFactory = subprocess.Popen,
        hf_api: Any | None = None,
    ):
        self.config = config
        self.store = store
        self._popen = popen
        self._hf_api = hf_api
        self._processes: dict[str, subprocess.Popen] = {}
        self._log_handles: dict[str, IO[bytes]] = {}
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def list_models(self) -> list[dict[str, object]]:
        recent = self.store.list_downloads(limit=50)
        candidates = {}
        for item in recent:
            repo_id = str(item.get("repo_id") or "").strip()
            if repo_id and repo_id not in candidates:
                candidates[repo_id] = {
                    "repo_id": repo_id,
                    "local_path": item.get("local_path"),
                    "last_download_id": item.get("id"),
                    "last_status": item.get("status"),
                    "updated_at": item.get("updated_at"),
                }
        return sorted(candidates.values(), key=lambda x: str(x["repo_id"]).lower())

    def list_remote_quants(self, repo_id: str, *, revision: str | None = None) -> list[dict[str, object]]:
        repo_id = self._normalize_repo_id(repo_id)
        files = self._get_hf_api().list_repo_tree(
            repo_id,
            recursive=True,
            expand=True,
            revision=revision or None,
            repo_type="model",
        )
        quants = []
        mmprojs = []
        for item in files:
            path = str(getattr(item, "path", ""))
            if not path.lower().endswith(".gguf"):
                continue
            entry = {
                "filename": Path(path).name,
                "path": path,
                "size_bytes": getattr(item, "size", None),
                "quant": self._quant_from_path(path),
            }
            if self._is_mmproj_path(path):
                mmprojs.append(entry)
            else:
                quants.append(entry)
        self._attach_mmprojs(quants, mmprojs)
        return sorted(quants, key=lambda item: str(item["path"]).lower())

    def start(
        self,
        repo_id: str,
        *,
        triggered_by: str = "unknown",
        revision: str | None = None,
        include_file: str | None = None,
    ) -> dict[str, object]:
        repo_id = self._normalize_repo_id(repo_id)
        include_file = self._normalize_include_file(include_file)
        revision = revision.strip() if revision else None
        for download_id, process in list(self._processes.items()):
            if process.poll() is not None:
                self._close_log(download_id)
                self._processes.pop(download_id, None)
        for active_id, process in self._processes.items():
            if process.poll() is None:
                active = self.store.get_download(active_id)
                if active["repo_id"] == repo_id:
                    raise ValueError(f"Download already running for {repo_id}")

        local_path = str(self._destination_for_repo(repo_id))
        command = self._command(repo_id, revision=revision, include_file=include_file)
        log_path = self._log_dir / f"{repo_id.replace('/', '__')}.log"
        record = self.store.create_download(
            repo_id=repo_id,
            revision=revision,
            local_path=local_path,
            command=" ".join(command),
            log_path=str(log_path),
            triggered_by=triggered_by,
        )
        download_id = str(record["id"])
        log_handle = log_path.open("ab")
        process = self._popen(command, stdout=log_handle, stderr=log_handle, cwd=None)
        self._processes[download_id] = process
        self._log_handles[download_id] = log_handle
        self.store.update_status(download_id, status="running", pid=process.pid)
        return self.status(download_id)

    def status(self, download_id: str) -> dict[str, object]:
        record = self.store.get_download(download_id)
        process = self._processes.get(download_id)
        if process is None:
            return record
        returncode = process.poll()
        if returncode is None:
            return record
        self._close_log(download_id)
        self._processes.pop(download_id, None)
        terminal = "succeeded" if returncode == 0 else "failed"
        updated = self.store.update_status(download_id, status=terminal, returncode=returncode, error_detail=None if returncode == 0 else f"Downloader exited with code {returncode}")
        return updated

    def tail_logs(self, download_id: str, lines: int = 200) -> str:
        record = self.status(download_id)
        log_path = Path(str(record["log_path"]))
        if not log_path.exists():
            return ""
        requested = max(1, min(lines, 2000))
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            return "".join(handle.readlines()[-requested:])

    def log_path(self, download_id: str) -> Path:
        record = self.status(download_id)
        return Path(str(record["log_path"]))

    def history(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        records = self.store.list_downloads(status=status, limit=limit)
        return [self.status(str(item["id"])) for item in records]

    def delete(self, download_id: str) -> None:
        record = self.status(download_id)
        if record["status"] == "running":
            raise ValueError("Cannot delete a running download")
        self._close_log(download_id)
        self._processes.pop(download_id, None)
        self.store.delete_download(download_id)

    def _destination_for_repo(self, repo_id: str) -> Path:
        root = self.config.model_roots[0]
        return root / repo_id.replace("/", "__")

    def _command(self, repo_id: str, *, revision: str | None, include_file: str | None = None) -> list[str]:
        target = str(self._destination_for_repo(repo_id))
        cmd = [self.config.python_bin, "-m", "huggingface_hub.cli.hf", "download", repo_id, "--local-dir", target]
        if revision:
            cmd.extend(["--revision", revision])
        if include_file:
            cmd.extend(["--include", include_file])
        return cmd

    def _normalize_repo_id(self, repo_id: str) -> str:
        repo_id = repo_id.strip()
        if not REPO_PATTERN.match(repo_id):
            raise ValueError("repo_id must be in owner/name format")
        return repo_id

    def _normalize_include_file(self, include_file: str | None) -> str | None:
        if not include_file:
            return None
        normalized = include_file.strip()
        if (
            not normalized
            or normalized.startswith("/")
            or "\\" in normalized
            or ".." in Path(normalized).parts
            or not normalized.lower().endswith(".gguf")
        ):
            raise ValueError("include_file must be a relative .gguf path")
        return normalized

    def _quant_from_path(self, path: str) -> str | None:
        parts = [part for part in Path(path).parts if part]
        candidates = parts[:-1] + [Path(path).stem]
        for candidate in candidates:
            match = GGUF_QUANT_PATTERN.search(candidate)
            if match:
                return match.group(1).upper()
        return None

    def _is_mmproj_path(self, path: str) -> bool:
        return "mmproj" in Path(path).name.lower()

    def _attach_mmprojs(self, quants: list[dict[str, object]], mmprojs: list[dict[str, object]]) -> None:
        if not mmprojs:
            return
        by_quant = {str(item.get("quant") or "").upper(): item for item in mmprojs}
        fallback = sorted(mmprojs, key=lambda item: int(item.get("size_bytes") or 0), reverse=True)[0]
        for item in quants:
            quant = str(item.get("quant") or "").upper()
            mmproj = by_quant.get(quant)
            if mmproj is None and quant == "BF16":
                mmproj = by_quant.get("F16")
            item["mmproj"] = mmproj or fallback

    def _get_hf_api(self) -> Any:
        if self._hf_api is None:
            try:
                self._hf_api = import_module("huggingface_hub").HfApi()
            except ImportError as exc:
                raise ValueError("huggingface_hub is not installed in this Python environment") from exc
        return self._hf_api

    @property
    def _log_dir(self) -> Path:
        return self.config.log_dir / "downloads"

    def _close_log(self, download_id: str) -> None:
        handle = self._log_handles.pop(download_id, None)
        if handle is not None and not handle.closed:
            handle.close()
