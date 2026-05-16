from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from llama_manager.api.dependencies import get_process_manager
from llama_manager.core.runtime.log_stream import stream_log_file
from llama_manager.core.runtime.process_manager import ProcessManager


router = APIRouter()


class FavoriteModelRequest(BaseModel):
    favorite: bool


@router.get("/models")
def list_models(manager: ProcessManager = Depends(get_process_manager)):
    return manager.list_statuses()


@router.post("/models/{name}/start")
def start_model(name: str, manager: ProcessManager = Depends(get_process_manager)):
    return _call_manager(manager.start, name)


@router.post("/models/{name}/stop")
def stop_model(name: str, manager: ProcessManager = Depends(get_process_manager)):
    return _call_manager(manager.stop, name)


@router.post("/models/{name}/restart")
def restart_model(name: str, manager: ProcessManager = Depends(get_process_manager)):
    return _call_manager(manager.restart, name)


@router.post("/models/{name}/favorite")
def favorite_model(
    name: str,
    body: FavoriteModelRequest,
    manager: ProcessManager = Depends(get_process_manager),
):
    return _call_manager(lambda model_name: manager.set_favorite(model_name, body.favorite), name)


@router.get("/logs/{name}")
def logs(name: str, lines: int = 200, manager: ProcessManager = Depends(get_process_manager)):
    try:
        return {"name": name, "text": manager.tail_logs(name, lines=lines)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/logs/{name}/stream")
def stream_logs(name: str, lines: int = 200, manager: ProcessManager = Depends(get_process_manager)):
    try:
        log_path = manager.log_path(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StreamingResponse(stream_log_file(log_path, lines=lines), media_type="text/event-stream")


def _call_manager(method, name: str):
    try:
        status = method(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if hasattr(status, "to_dict"):
        return status.to_dict()
    return status
