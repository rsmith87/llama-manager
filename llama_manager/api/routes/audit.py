from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi import Request
from pydantic import BaseModel, Field

from llama_manager.api.dependencies import get_audit_store
from llama_manager.core.persistence.audit_store_orm import AuditStoreOrm

router = APIRouter(prefix="/audit")


class AuditEventRequest(BaseModel):
    actor: str = Field(default="ui")
    event_type: str = Field(min_length=1, max_length=80)
    dry_run: bool = False
    target: str | None = None
    route: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)


@router.get("/events")
async def list_audit_events(
    limit: int = Query(default=100, ge=1, le=1000),
    event_type: str | None = Query(default=None),
    target: str | None = Query(default=None),
    dry_run: bool | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    store: AuditStoreOrm = Depends(get_audit_store),
):
    return store.list_events(
        limit=limit,
        event_type=event_type,
        target=target,
        dry_run=dry_run,
        created_from=created_from,
        created_to=created_to,
    )


@router.post("/events")
async def create_audit_event(
    body: AuditEventRequest,
    request: Request,
    store: AuditStoreOrm = Depends(get_audit_store),
):
    actor = getattr(request.state, "ui_user", None) or body.actor
    return store.create_event(
        actor=actor,
        event_type=body.event_type,
        dry_run=body.dry_run,
        target=body.target,
        route=body.route,
        payload=body.payload,
    )
