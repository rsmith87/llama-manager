from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class InMemoryStore:
    """In-memory store used for tests and non-persistent runs."""

    def __init__(self):
        self._data: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        return dict(self._data)

    def save(self, data: dict[str, Any]) -> None:
        self._data = dict(data)


class JsonFileStore:
    """Simple JSON-backed store for controller dynamic state."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return {}
        return payload

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
