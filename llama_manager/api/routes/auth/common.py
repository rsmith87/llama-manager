from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request


def get_auth_store(request: Request) -> Any:
    return request.app.state.auth_store


def require_session(request: Request) -> dict:
    token = request.headers.get("X-UI-Session")
    session = request.app.state.ui_sessions.get(token or "")
    if not session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    expires_at = session.get("expires_at")
    if expires_at and datetime.now(UTC) > datetime.fromisoformat(expires_at):
        request.app.state.ui_sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="Session expired")
    return session


def require_admin_session(request: Request) -> dict:
    session = require_session(request)
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return session
