from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from llama_manager.core.orchestration.orchestrator import Orchestrator


TERMINAL_STATUSES = {"completed", "failed", "timed_out", "canceled"}


def encode_sse(event: dict) -> str:
    return (
        f"id: {event['id']}\n"
        f"event: {event['event_type']}\n"
        f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
    )


async def stream_job_events(orchestrator: Orchestrator, job_id: str, poll_interval_seconds: float = 0.25) -> AsyncIterator[str]:
    seen: set[str] = set()
    while True:
        for event in orchestrator.list_events(job_id, limit=1000):
            event_id = str(event["id"])
            if event_id in seen:
                continue
            seen.add(event_id)
            yield encode_sse(event)
        job = orchestrator.get_job(job_id)
        if job.get("status") in TERMINAL_STATUSES:
            break
        await asyncio.sleep(poll_interval_seconds)
