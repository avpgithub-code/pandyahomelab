"""Public page-view / engagement beacon — POST /feedback/pv.

Sent by feedback-widget.js (embedded on every page), so a row only exists when a
browser actually executed the page's JavaScript. That filters out the scanners
and HTML-only bots that dominate the nginx access log.

Two message types, both JSON (sent as text/plain via navigator.sendBeacon):
  {"t":"start",  "pv":…, "v":…, "p":"/path/", "r":"<document.referrer>",
                 "us":…, "um":…, "uc":…, "w":<viewport px>, "l":"en-US"}
  {"t":"update", "pv":…, "v":…, "e":<engaged ms>, "s":<max scroll %>, "i":<interactions>}

No cookies. Visitor identity is the salted IP hash (same as the rest of analytics);
`v` is a random id held in sessionStorage, so it dies with the tab.
"""
import json
import logging
import re
from typing import Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Request, Response

from app.bot_filter import is_bot
from app.engagement_queries import (
    count_recent_starts,
    insert_page_view,
    update_page_view,
)
from app.ip_hasher import hash_request_ip

logger = logging.getLogger("admin-portal.beacon")
router = APIRouter(prefix="/feedback", tags=["beacon"])

ID_RE = re.compile(r"^[a-z0-9]{16}$")
MAX_BODY_BYTES = 2048
MAX_STARTS_PER_IP_10MIN = 120        # a human clicking through every page stays far below this
MAX_ENGAGED_MS = 60 * 60 * 1000      # cap one page view at an hour of engagement


def _clip(v, n: int) -> Optional[str]:
    if v is None:
        return None
    v = str(v).strip()[:n]
    return v or None


def _int(v, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return lo


def _referrer_domain(ref: Optional[str]) -> Optional[str]:
    if not ref:
        return None
    host = (urlsplit(ref).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host[:255] or None


def _device(width: int) -> Optional[str]:
    if width <= 0:
        return None
    if width < 768:
        return "mobile"
    if width < 1100:
        return "tablet"
    return "desktop"


@router.post("/pv", status_code=204)
async def page_view_beacon(request: Request) -> Response:
    """Always answers 204 — the beacon is fire-and-forget; bad input is dropped silently."""
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        return Response(status_code=204)
    try:
        msg = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return Response(status_code=204)
    if not isinstance(msg, dict):
        return Response(status_code=204)

    pv, visit = str(msg.get("pv", "")), str(msg.get("v", ""))
    if not (ID_RE.match(pv) and ID_RE.match(visit)):
        return Response(status_code=204)

    ip_hash = hash_request_ip(request)

    if msg.get("t") == "start":
        page_id = _clip(msg.get("p"), 255)
        if not page_id or not page_id.startswith("/"):
            return Response(status_code=204)
        if count_recent_starts(ip_hash) >= MAX_STARTS_PER_IP_10MIN:
            return Response(status_code=204)
        ua = _clip(request.headers.get("user-agent"), 512)
        country = _clip(request.headers.get("cf-ipcountry"), 2)
        insert_page_view({
            "pv_id":           pv,
            "visit_id":        visit,
            "ip_hash":         ip_hash,
            "country":         country if country and country.isalpha() else None,
            "page_id":         page_id,
            "referrer_domain": _referrer_domain(_clip(msg.get("r"), 1024)),
            "utm_source":      _clip(msg.get("us"), 100),
            "utm_medium":      _clip(msg.get("um"), 100),
            "utm_campaign":    _clip(msg.get("uc"), 100),
            "device":          _device(_int(msg.get("w"), 0, 20000)),
            "lang":            _clip(msg.get("l"), 16),
            "user_agent":      ua,
            "is_bot":          is_bot(ua or ""),
        })
    elif msg.get("t") == "update":
        interactions = _int(msg.get("i"), 0, 100000)
        update_page_view(
            pv_id=pv,
            ip_hash=ip_hash,
            engaged_ms=_int(msg.get("e"), 0, MAX_ENGAGED_MS),
            max_scroll_pct=_int(msg.get("s"), 0, 100),
            interactions=interactions,
        )
    return Response(status_code=204)
