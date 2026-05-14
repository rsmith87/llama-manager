from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from llama_manager.api.routes.auth.common import get_auth_store, require_admin_session


router = APIRouter(prefix="/auth")


class CreateKeyRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    role: str = Field(default="operator")


@router.get("/keys")
def list_keys(request: Request):
    require_admin_session(request)
    return get_auth_store(request).list_keys()


@router.post("/keys")
def create_key(body: CreateKeyRequest, request: Request):
    session = require_admin_session(request)
    created = get_auth_store(request).create_key(body.username, body.role)
    request.app.state.audit_store.create_event(
        actor=session.get("username", "unknown"),
        event_type="auth_key_create",
        dry_run=False,
        target=body.username,
        route="auth",
        payload={"role": body.role, "key_id": created["id"]},
    )
    return created


@router.post("/keys/{key_id}/revoke")
def revoke_key(key_id: str, request: Request):
    session = require_admin_session(request)
    ok = get_auth_store(request).revoke_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Key not found")
    request.app.state.audit_store.create_event(
        actor=session.get("username", "unknown"),
        event_type="auth_key_revoke",
        dry_run=False,
        target=key_id,
        route="auth",
        payload={},
    )
    return {"ok": True}
