from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from llama_manager.api.routes.auth.common import get_auth_store, require_session


router = APIRouter(prefix="/auth")
SESSION_TTL_HOURS = 12


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    api_key: str = Field(min_length=1, max_length=200)


@router.post("/login")
def login(body: LoginRequest, request: Request):
    store = get_auth_store(request)
    resolved = store.resolve_key(body.api_key)
    configured = request.app.state.config.agent_api_key
    if resolved is None:
        request.app.state.audit_store.create_event(
            actor=body.username,
            event_type="auth_login_failed",
            dry_run=False,
            target=body.username,
            route="auth",
            payload={},
        )
        if configured and not secrets.compare_digest(body.api_key, configured):
            raise HTTPException(status_code=401, detail="Invalid API key")
        if not configured:
            raise HTTPException(status_code=401, detail="Invalid API key")
    role = resolved["role"] if resolved else "admin"
    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now(UTC) + timedelta(hours=SESSION_TTL_HOURS)).isoformat()
    request.app.state.ui_sessions[token] = {
        "username": body.username,
        "created_at": datetime.now(UTC).isoformat(),
        "expires_at": expires_at,
        "role": role,
    }
    request.app.state.audit_store.create_event(
        actor=body.username,
        event_type="auth_login",
        dry_run=False,
        target=body.username,
        route="auth",
        payload={"role": role},
    )
    return {"token": token, "username": body.username, "expires_at": expires_at, "role": role}


@router.get("/me")
def me(request: Request):
    session = require_session(request)
    return {
        "username": session["username"],
        "created_at": session["created_at"],
        "role": session.get("role", "operator"),
    }


@router.post("/logout")
def logout(request: Request):
    token = request.headers.get("X-UI-Session")
    if token:
        session = request.app.state.ui_sessions.pop(token, None)
        if session:
            request.app.state.audit_store.create_event(
                actor=session.get("username", "unknown"),
                event_type="auth_logout",
                dry_run=False,
                target=session.get("username", "unknown"),
                route="auth",
                payload={},
            )
    return {"ok": True}
