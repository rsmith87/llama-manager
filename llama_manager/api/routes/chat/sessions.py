from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from llama_manager.api.dependencies import get_chat_session_store
from llama_manager.api.routes.chat.common import SaveChatSessionRequest


router = APIRouter(prefix="/chat")


@router.get("/sessions")
async def list_chat_sessions(store: Any = Depends(get_chat_session_store)):
    return store.list_sessions()


@router.get("/sessions/{session_id}")
async def get_chat_session(session_id: str, store: Any = Depends(get_chat_session_store)):
    payload = store.get_session(session_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return payload


@router.post("/sessions")
async def save_chat_session(
    body: SaveChatSessionRequest,
    store: Any = Depends(get_chat_session_store),
):
    return store.save_session(
        session_id=body.id,
        name=body.name,
        model=body.model,
        target_selector=body.target,
        messages=[item.model_dump() for item in body.messages],
        request_defaults=body.request_defaults,
    )


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    store: Any = Depends(get_chat_session_store),
):
    deleted = store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True, "id": session_id}
