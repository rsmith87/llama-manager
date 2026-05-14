from __future__ import annotations

from fastapi import APIRouter

from llama_manager.api.routes.auth import keys, sessions


router = APIRouter()
router.include_router(sessions.router)
router.include_router(keys.router)
