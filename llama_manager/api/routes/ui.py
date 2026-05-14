from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles


UI_DIR = Path(__file__).resolve().parents[2] / "ui"

router = APIRouter()
static_app = StaticFiles(directory=UI_DIR)


@router.get("/", include_in_schema=False)
def index():
    return FileResponse(UI_DIR / "index.html")


@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
