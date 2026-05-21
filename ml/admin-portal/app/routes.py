"""Routes: GET / (dashboard), GET /health."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth import get_current_admin
from app.queries import (
    fetch_countries,
    fetch_daily,
    fetch_referrers,
    fetch_summary,
    fetch_top_paths,
)

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
    countries = fetch_countries(days, limit=10)
    referrers = fetch_referrers(days, limit=10)

    # Daily data for Chart.js — chronological order, dates as strings, ints as ints.
    daily_chart = [
        {
            "day": str(r["day"]),
            "real": int(r["real_events"] or 0),
            "bots": int(r["bot_events"] or 0),
        }
        for r in reversed(daily)
    ]
    countries_chart = [
        {"country": r["country"], "visitors": int(r["visitors"] or 0)}
        for r in countries
    ]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "days": days,
            "admin": admin,
            "summary": summary,
            "daily": daily,
            "top_paths": top_paths,
            "countries": countries,
            "referrers": referrers,
            "daily_chart_json": json.dumps(daily_chart),
            "countries_chart_json": json.dumps(countries_chart),
        },
    )
