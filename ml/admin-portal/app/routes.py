"""Admin routes (all under /admin/ prefix when mounted).

Externally:
    GET  /admin/                    → dashboard (analytics)
    GET  /admin/feedback            → moderation list (recent comments)
    POST /admin/feedback/{id}/hide  → toggle hidden flag (form submit)
"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import get_current_admin
from app.feedback_queries import (
    fetch_feedback_summary,
    fetch_recent_comments,
    toggle_comment_hidden,
)
from app.queries import (
    fetch_countries,
    fetch_daily,
    fetch_referrers,
    fetch_summary,
    fetch_top_paths,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


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


@router.get("/feedback", response_class=HTMLResponse)
async def feedback_moderation(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    admin: str = Depends(get_current_admin),
):
    summary = fetch_feedback_summary()
    comments = fetch_recent_comments(limit=limit)
    return templates.TemplateResponse(
        "moderation.html",
        {
            "request": request,
            "admin": admin,
            "limit": limit,
            "summary": summary,
            "comments": comments,
        },
    )


@router.post("/feedback/{comment_id}/hide")
async def feedback_toggle_hidden(
    comment_id: int,
    admin: str = Depends(get_current_admin),
):
    """POST from the moderation form. Flips hidden, redirects back."""
    toggle_comment_hidden(comment_id)
    # 303 See Other → POST→GET redirect (avoids the form resubmit prompt)
    return RedirectResponse(url="/admin/feedback", status_code=303)
