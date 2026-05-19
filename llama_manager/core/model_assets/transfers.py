from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, BinaryIO

from llama_manager.core.config import AppConfig
from llama_manager.core.model_assets.library import GgufLibrary


class TransferManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self.library = GgufLibrary(config)
        self._grants: dict[str, dict[str, str]] = {}

    def build_manifest(self, file_id: str) -> dict[str, Any]:
        source = self._path_for_id(file_id)
        root = self._root_for_path(source)
        relative = source.relative_to(root)
        model_dir = relative.parts[0] if len(relative.parts) > 1 else None
        logical_dir = root / model_dir if model_dir else root
        files = self._manifest_paths(source=source, logical_dir=logical_dir, model_dir=model_dir)
        return {
            "source_file_id": file_id,
            "filename": source.name,
            "model_dir": model_dir,
            "include": "selected_with_sidecars",
            "files": [self._manifest_file(path, root) for path in files],
        }

    def _manifest_paths(self, *, source: Path, logical_dir: Path, model_dir: str | None) -> list[Path]:
        paths: set[Path] = {source}
        if model_dir is not None:
            for path in logical_dir.iterdir():
                if path.is_file() and path.suffix.lower() != ".gguf":
                    paths.add(path)
        for model in self.config.models.values():
            if Path(model.path) == source and model.mmproj:
                mmproj = Path(model.mmproj)
                if mmproj.exists() and self._is_under_model_roots(mmproj):
                    paths.add(mmproj)
        return sorted(paths, key=lambda item: str(item.relative_to(self._root_for_path(item))).lower())

    def _manifest_file(self, path: Path, root: Path) -> dict[str, Any]:
        stat = path.stat()
        return {
            "id": self.file_token(path),
            "relative_path": path.relative_to(root).as_posix(),
            "filename": path.name,
            "size_bytes": stat.st_size,
            "sha256": self.sha256(path),
        }

    def _path_for_id(self, file_id: str) -> Path:
        for path in self.library._gguf_paths():
            if self.library.file_id(path) == file_id:
                return path
        raise KeyError(f"Unknown GGUF file id: {file_id}")

    def file_for_token(self, token: str) -> Path:
        for root in self.config.model_roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.is_file() and self.file_token(path) == token:
                    return path
        raise KeyError(f"Unknown transfer file id: {token}")

    def write_manifest_file(self, manifest_file: dict[str, Any], stream: BinaryIO) -> dict[str, Any]:
        destination = self.destination_path(str(manifest_file["relative_path"]))
        expected_size = int(manifest_file["size_bytes"])
        expected_sha256 = str(manifest_file["sha256"])
        if destination.exists():
            if destination.stat().st_size == expected_size and self.sha256(destination) == expected_sha256:
                return {
                    "status": "skipped",
                    "path": str(destination),
                    "bytes": expected_size,
                    "sha256": expected_sha256,
                }
            raise FileExistsError(f"Destination conflict: {destination}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path = destination.with_name(f".{destination.name}.tmp")
        digest = hashlib.sha256()
        total = 0
        with temp_path.open("wb") as handle:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                total += len(chunk)
                digest.update(chunk)
                handle.write(chunk)
        actual_sha256 = digest.hexdigest()
        if total != expected_size or actual_sha256 != expected_sha256:
            temp_path.unlink(missing_ok=True)
            raise ValueError("Transferred file failed size or sha256 verification")
        os.replace(temp_path, destination)
        return {
            "status": "copied",
            "path": str(destination),
            "bytes": total,
            "sha256": actual_sha256,
        }

    def destination_path(self, relative_path: str) -> Path:
        if not self.config.model_roots:
            raise ValueError("Destination model root missing")
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Unsafe relative path: {relative_path}")
        return self.config.model_roots[0] / relative

    def create_grant(self, source_file_id: str, transfer_token: str, destination_node: str) -> None:
        manifest = self.build_manifest(source_file_id)
        file_ids = {str(item["id"]) for item in manifest["files"]}
        self._grants[transfer_token] = {
            "source_file_id": source_file_id,
            "destination_node": destination_node,
            "file_ids": ",".join(sorted(file_ids)),
        }

    def require_grant(self, source_file_id: str, authorization: str | None) -> None:
        token = self._bearer_token(authorization)
        grant = self._grants.get(token)
        if not grant or grant["source_file_id"] != source_file_id:
            raise PermissionError("Invalid transfer token")

    def require_file_grant(self, path: Path, authorization: str | None) -> None:
        token = self._bearer_token(authorization)
        grant = self._grants.get(token)
        if not grant:
            raise PermissionError("Invalid transfer token")
        if self.file_token(path) not in set(grant["file_ids"].split(",")):
            raise PermissionError("Transfer token does not allow this file")

    def file_token(self, path: Path) -> str:
        root = self._root_for_path(path)
        return hashlib.sha256(str(path.relative_to(root)).encode("utf-8")).hexdigest()[:24]

    def _root_for_path(self, path: Path) -> Path:
        resolved = path.resolve()
        for root in self.config.model_roots:
            root_resolved = root.resolve()
            if resolved == root_resolved or root_resolved in resolved.parents:
                return root
        raise ValueError(f"Path is outside configured model roots: {path}")

    def _is_under_model_roots(self, path: Path) -> bool:
        try:
            self._root_for_path(path)
            return True
        except ValueError:
            return False

    @staticmethod
    def _bearer_token(authorization: str | None) -> str:
        prefix = "Bearer "
        if not authorization or not authorization.startswith(prefix):
            raise PermissionError("Missing transfer token")
        return authorization[len(prefix):]

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
