from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from llama_manager.api.dependencies import get_thread_service
from llama_manager.core.threads.models import CreateThreadRequest, ThreadMessageRequest
from llama_manager.core.threads.service import ThreadService


router = APIRouter(prefix="/threads")


@router.post("", status_code=201)
def create_thread(
    body: CreateThreadRequest,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
):
    try:
        return service.create_thread(
            title=body.title,
            default_model=body.default_model,
            metadata=body.metadata.model_dump(),
            created_by=getattr(request.state, "ui_user", None),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{thread_id}/events")
def list_events(
    thread_id: str,
    request: Request,
    include_internal: bool = Query(default=False),
    service: ThreadService = Depends(get_thread_service),
):
    if include_internal and getattr(request.state, "ui_role", None) != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        return service.list_events(thread_id, include_internal=include_internal)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{thread_id}/messages")
async def post_message(
    thread_id: str,
    body: ThreadMessageRequest,
    service: ThreadService = Depends(get_thread_service),
):
    try:
        return await service.post_message_async(
            thread_id=thread_id,
            role=body.role,
            content=body.content,
            model=body.model,
            target=body.target,
            metadata=body.metadata.model_dump() if body.metadata is not None else None,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
