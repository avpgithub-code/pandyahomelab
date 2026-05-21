"""Routes: GET / (dashboard), GET /health."""
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth import get_current_admin
from app.queries import fetch_daily, fetch_summary, fetch_top_paths

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/health")
async def health():
    return {"status": "healthy"}


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    admin: str = Depends(get_current_admin),
):
    summary = fetch_summary(days)
    daily = fetch_daily(days)
    top_paths = fetch_top_paths(days, limit=5)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "days": days,
            "admin": admin,
            "summary": summary,
            "daily": daily,
            "top_paths": top_paths,
        },
    )
