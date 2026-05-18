from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from llama_manager.api.dependencies import get_download_manager
from llama_manager.core.model_assets.downloads import DownloadManager
from llama_manager.core.runtime.log_stream import stream_log_file


class StartDownloadRequest(BaseModel):
    revision: str | None = None


router = APIRouter(prefix="/downloads")


@router.get("/models")
def list_download_models(manager: DownloadManager = Depends(get_download_manager)):
    return manager.list_models()


@router.get("/history")
def download_history(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    manager: DownloadManager = Depends(get_download_manager),
):
    return manager.history(status=status, limit=limit)


@router.post("/{repo_id:path}/start")
def start_download(
    repo_id: str,
    request: Request,
    body: StartDownloadRequest | None = None,
    manager: DownloadManager = Depends(get_download_manager),
):
    try:
        actor = getattr(request.state, "ui_user", "unknown")
        revision = body.revision if body else None
        return manager.start(repo_id, triggered_by=actor, revision=revision)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{download_id}")
def get_download(download_id: str, manager: DownloadManager = Depends(get_download_manager)):
    try:
        return manager.status(download_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{download_id}/logs")
def download_logs(download_id: str, lines: int = 200, manager: DownloadManager = Depends(get_download_manager)):
    try:
        return {"id": download_id, "text": manager.tail_logs(download_id, lines=lines)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{download_id}/logs/stream")
def stream_download_logs(
    download_id: str,
    lines: int = 200,
    manager: DownloadManager = Depends(get_download_manager),
):
    try:
        log_path = manager.log_path(download_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StreamingResponse(stream_log_file(log_path, lines=lines), media_type="text/event-stream")


@router.delete("/{download_id}")
def delete_download(download_id: str, manager: DownloadManager = Depends(get_download_manager)):
    try:
        manager.delete(download_id)
        return {"id": download_id, "deleted": True}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
