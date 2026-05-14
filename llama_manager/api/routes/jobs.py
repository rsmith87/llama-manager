from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from pydantic import BaseModel, Field

from llama_manager.api.dependencies import get_orchestrator
from llama_manager.core.orchestration.event_stream import stream_job_events
from llama_manager.core.orchestration.job_contracts import validate_job_payload
from llama_manager.core.orchestration.orchestrator import Orchestrator


router = APIRouter()


class CreateJobRequest(BaseModel):
    type: str
    payload: dict
    priority: int = 0
    target: str = "auto"
    requested_by: str | None = None


class CancelJobResponse(BaseModel):
    id: str
    status: str


@router.post("/jobs", status_code=201)
def create_job(body: CreateJobRequest, orchestrator: Orchestrator = Depends(get_orchestrator)):
    try:
        payload = validate_job_payload(body.type, body.payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    return orchestrator.create_job(
        job_type=body.type,
        payload=payload,
        priority=body.priority,
        target=body.target,
        requested_by=body.requested_by,
    )


@router.get("/jobs")
def list_jobs(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    return orchestrator.list_jobs(status=status, limit=limit)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, orchestrator: Orchestrator = Depends(get_orchestrator)):
    try:
        return orchestrator.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, orchestrator: Orchestrator = Depends(get_orchestrator)):
    try:
        return orchestrator.cancel_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/events")
def job_events(
    job_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    return orchestrator.list_events(job_id, limit=limit)


@router.get("/jobs/{job_id}/events/stream")
def job_events_stream(job_id: str, orchestrator: Orchestrator = Depends(get_orchestrator)):
    try:
        orchestrator.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StreamingResponse(stream_job_events(orchestrator, job_id), media_type="text/event-stream")


@router.get("/controller/stats")
def controller_stats(orchestrator: Orchestrator = Depends(get_orchestrator)):
    return orchestrator.controller_stats()


@router.get("/jobs/{job_id}/artifacts")
def job_artifacts(job_id: str, orchestrator: Orchestrator = Depends(get_orchestrator)):
    try:
        return orchestrator.get_job(job_id).get("artifacts", [])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/controller/retention-policy")
def retention_policy(orchestrator: Orchestrator = Depends(get_orchestrator)):
    return {
        "retention_days": orchestrator.retention_days,
        "archive_retention_days": orchestrator.archive_retention_days,
    }


@router.post("/controller/archive/export")
def export_archive(
    retention_days: int | None = None,
    limit: int = Query(default=1000, ge=1, le=10000),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive_path = str(Path("./logs/archive") / f"jobs-archive-{stamp}.jsonl")
    return orchestrator.archive_snapshot(archive_path=archive_path, retention_days=retention_days, limit=limit)
