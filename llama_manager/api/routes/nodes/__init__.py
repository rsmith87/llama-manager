from __future__ import annotations

from fastapi import APIRouter

from llama_manager.api.routes.nodes import admin, aggregate, proxy


router = APIRouter()
router.include_router(admin.router)
router.include_router(aggregate.router)
router.include_router(proxy.router)
