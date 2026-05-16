from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path


def encode_sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


async def stream_log_file(path: Path, lines: int = 200, poll_interval_seconds: float = 0.25) -> AsyncIterator[str]:
    requested = max(1, min(lines, 2000))
    start = 0
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            recent = handle.readlines()[-requested:]
            if recent:
                yield encode_sse("chunk", {"text": "".join(recent)})
            start = handle.tell()

    while True:
        if path.exists():
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(start)
                text = handle.read()
                start = handle.tell()
                if text:
                    yield encode_sse("chunk", {"text": text})
        yield ": keepalive\n\n"
        await asyncio.sleep(poll_interval_seconds)
