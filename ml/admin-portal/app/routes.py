"""Admin routes (all under /admin/ prefix when mounted).

Externally:
    GET  /admin/                    → dashboard (analytics)
    GET  /admin/feedback            → moderation list (recent comments)
    POST /admin/feedback/{id}/hide  → toggle hidden flag (form submit)
"""
import json
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import get_current_admin
from app.engagement_queries import (
    fetch_devices,
    fetch_engagement_buckets,
    fetch_engagement_daily,
    fetch_engagement_summary,
    fetch_home_pages,
    fetch_home_summary,
    fetch_human_countries,
    fetch_journeys,
    fetch_next_pages,
    fetch_page_actions,
    fetch_page_engagement,
    fetch_visit_sources,
)
from app.feedback_queries import (
    fetch_feedback_by_page,
    fetch_recent_likes,
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


def _flag(code: Optional[str]) -> str:
    """'IN' → 🇮🇳 (regional-indicator pair); anything else → ''."""
    if not code or len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


templates.env.filters["flag"] = _flag


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

    # Beacon-verified humans (feedback-widget.js) — the numbers to trust
    human = fetch_engagement_summary(days)
    human_daily = fetch_engagement_daily(days)
    pages = fetch_page_engagement(days, limit=20)
    actions = fetch_page_actions(days, limit=25)
    journeys = fetch_journeys(days, limit=10)
    next_pages = fetch_next_pages(days, limit=15)
    sources = fetch_visit_sources(days, limit=10)
    human_countries = fetch_human_countries(days, limit=10)
    devices = fetch_devices(days)
    buckets = fetch_engagement_buckets(days)
    home = fetch_home_summary(days)
    home_pages = fetch_home_pages(days, limit=10)

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
        for r in human_countries
    ]
    human_chart = [
        {
            "day": str(r["day"]),
            "visitors": int(r["visitors"] or 0),
            "page_views": int(r["page_views"] or 0),
        }
        for r in reversed(human_daily)
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
            "human": human,
            "human_daily": human_daily,
            "pages": pages,
            "actions": actions,
            "journeys": journeys,
            "next_pages": next_pages,
            "sources": sources,
            "human_countries": human_countries,
            "devices": devices,
            "buckets": buckets,
            "home": home,
            "home_pages": home_pages,
            "human_chart_json": json.dumps(human_chart),
            "buckets_json": json.dumps(buckets),
            "daily_chart_json": json.dumps(daily_chart),
            "countries_chart_json": json.dumps(countries_chart),
        },
    )


@router.get("/feedback", response_class=HTMLResponse)
async def feedback_moderation(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    page: Optional[str] = Query(None, max_length=255),
    admin: str = Depends(get_current_admin),
):
    page = page or None
    summary = fetch_feedback_summary()
    by_page = fetch_feedback_by_page()
    comments = fetch_recent_comments(limit=limit, page=page)
    likes = fetch_recent_likes(limit=limit, page=page)
    return templates.TemplateResponse(
        "moderation.html",
        {
            "request": request,
            "admin": admin,
            "limit": limit,
            "page": page,
            "page_q": quote(page, safe="") if page else "",
            "summary": summary,
            "by_page": by_page,
            "comments": comments,
            "likes": likes,
        },
    )


@router.post("/feedback/{comment_id}/hide")
async def feedback_toggle_hidden(
    comment_id: int,
    page: Optional[str] = Query(None, max_length=255),
    admin: str = Depends(get_current_admin),
):
    """POST from the moderation form. Flips hidden, redirects back (keeping the page filter)."""
    toggle_comment_hidden(comment_id)
    back = "/admin/feedback" + (f"?page={quote(page, safe='')}" if page else "")
    # 303 See Other → POST→GET redirect (avoids the form resubmit prompt)
    return RedirectResponse(url=back, status_code=303)
