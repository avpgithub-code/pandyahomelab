"""cricstat section of the admin portal (P0.3b), all under /admin/cricket (Basic Auth).

    GET  /admin/cricket                       → jobs, data overview, golden summary
    GET  /admin/cricket/golden                → golden review table (filters: q, status)
    POST /admin/cricket/golden/verify         → start Verify References (one run at a time)
    POST /admin/cricket/golden/save           → save one block's references / explanations
    POST /admin/cricket/golden/accept-agreeing → accept every suggestion that equals our figure
    POST /admin/cricket/golden/explain-coverage → accept + explain coverage-gap blocks in bulk
    POST /admin/cricket/golden/check          → run the golden check now
    GET  /admin/cricket/golden.csv            → export (same columns as docs/validation)

Data comes from cricstat-api's internal /v1/admin/* endpoints over cricstat-network; references
and suggestions live in Postgres (schema cricstat). POSTs refuse cross-site requests: the browser
re-sends Basic Auth credentials on its own, so a same-origin check stands in for a CSRF token.
"""
import json
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, quote, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth import get_current_admin
from app.cricstat import api_client, golden, runner, store

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
STATUSES = ("", "match", "explained", "stale", "DIFF", "unchecked", "suggested")


def same_origin(request: Request) -> None:
    """Reject POSTs whose Origin/Referer is another site (or missing)."""
    src = request.headers.get("origin") or request.headers.get("referer") or ""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    if not src or urlparse(src).netloc != host:
        raise HTTPException(status_code=403, detail="cross-site request refused")


async def form(request: Request) -> dict:
    body = (await request.body()).decode("utf-8")
    return {k: v[-1] for k, v in parse_qs(body, keep_blank_values=True).items()}


def back(path: str, msg: str = "", anchor: str = "") -> RedirectResponse:
    url = path + (("?msg=" + quote(msg)) if msg else "") + (("#" + anchor) if anchor else "")
    return RedirectResponse(url=url, status_code=303)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def cricket_home(request: Request, msg: str = "",
                       admin: str = Depends(get_current_admin)):
    ctx = {"request": request, "admin": admin, "error": None, "msg": msg}
    try:
        ctx["jobs"] = api_client.get("/v1/admin/jobs")
        ctx["overview"] = api_client.get("/v1/admin/overview")
        view = runner.golden_view()
        ctx["golden"] = view["summary"]
        ctx["window_to"] = view["window_to"]
    except api_client.CricstatUnavailable as exc:
        ctx["error"] = str(exc)
    ctx["runs"] = store.runs(8)
    ctx["chart"] = json.dumps(_chart(ctx.get("overview")))
    return templates.TemplateResponse("cricket.html", ctx)


def _chart(overview: Optional[dict]) -> dict:
    """Matches per year by format group, men and women (shows the coverage gaps)."""
    groups = {"TEST": "Test", "ODI": "ODI", "T20I": "T20I", "T20_LEAGUE": "Leagues",
              "HUNDRED": "Leagues"}
    out = {}
    for g in ("male", "female"):
        years, series = [], {}
        for r in (overview or {}).get("matches_per_year", []):
            if r["gender"] != g:
                continue
            if r["year"] not in years:
                years.append(r["year"])
            label = groups.get(r["format_key"], "Other")
            series.setdefault(label, {})[r["year"]] = series.get(label, {}).get(
                r["year"], 0) + r["matches"]
        out[g] = {"years": years, "series": {k: [v.get(y, 0) for y in years]
                                             for k, v in series.items()}}
    return out


@router.get("/golden", response_class=HTMLResponse)
async def golden_page(request: Request, q: str = Query("", max_length=60),
                      status: str = Query("", max_length=12), msg: str = "",
                      admin: str = Depends(get_current_admin)):
    ctx = {"request": request, "admin": admin, "q": q, "status": status, "msg": msg,
           "statuses": STATUSES, "error": None, "blocks": [], "summary": {}}
    try:
        view = runner.golden_view()
        ctx.update(window_to=view["window_to"], summary=view["summary"],
                   missing=view["missing"])
        blocks = view["blocks"]
        if q:
            blocks = [b for b in blocks if q.lower() in b["name"].lower()]
        if status == "unchecked":
            blocks = [b for b in blocks if any(not s for s in b["statuses"])]
        elif status == "suggested":
            blocks = [b for b in blocks if any(r["suggestion"] and not r["reference"]
                                               for r in b["rows"])]
        elif status:
            blocks = [b for b in blocks if status in b["statuses"]]
        ctx["blocks"] = blocks
    except api_client.CricstatUnavailable as exc:
        ctx["error"] = str(exc)
    ctx["verify"] = store.last_run("verify")
    ctx["check"] = store.last_run("check")
    return templates.TemplateResponse("cricket_golden.html", ctx)


@router.post("/golden/verify")
async def golden_verify(request: Request, admin: str = Depends(get_current_admin)):
    same_origin(request)
    run_id = runner.start_verify()
    msg = ("Verify References started (run %d): about a minute for the whole selection."
           % run_id) if run_id else "A Verify References run is already in progress."
    return back("/admin/cricket/golden", msg)


@router.post("/golden/save")
async def golden_save(request: Request, admin: str = Depends(get_current_admin)):
    """One block: for each metric, reference / source / explanation, or 'clear'."""
    same_origin(request)
    f = await form(request)
    entity, scope = f.get("entity_id", ""), f.get("scope", "")
    view = runner.golden_view()
    block = next((b for b in view["blocks"] if b["id"] == entity and b["scope"] == scope), None)
    if block is None:
        raise HTTPException(status_code=404, detail="unknown block")
    today = date.today().isoformat()
    saved = 0
    for row in block["rows"]:
        m = row["metric"]
        key = (entity, scope, m)
        if f.get("clear__" + m):
            store.delete_reference(key)
            saved += 1
            continue
        ref = f.get("ref__" + m, "").strip()
        if f.get("accept__" + m) and row["suggestion"]:
            ref = row["suggestion"]
            source = "Wikipedia infobox, as of %s" % (row["suggestion_as_of"] or "?")
        else:
            source = f.get("src__" + m, "").strip() or row["source"]
        expl = f.get("expl__" + m, "").strip()
        if not ref:
            continue
        if (ref, source, expl) == (row["reference"], row["source"], row["explanation"]):
            continue
        store.save_reference(key, ref, source, today, expl, row["ours"], block["mat"])
        saved += 1
    return back("/admin/cricket/golden", "Saved %d row(s) for %s %s." % (saved, block["name"],
                                                                         scope),
                anchor="b-%s-%s" % (entity.replace("|", "-"), scope))


@router.post("/golden/accept-agreeing")
async def golden_accept_agreeing(request: Request, admin: str = Depends(get_current_admin)):
    same_origin(request)
    view = runner.golden_view()
    today, n = date.today().isoformat(), 0
    for b in view["blocks"]:
        for r in b["rows"]:
            if r["suggestion_agrees"] and not r["reference"]:
                store.save_reference((b["id"], b["scope"], r["metric"]), r["suggestion"],
                                     "Wikipedia infobox, as of %s" % (r["suggestion_as_of"]
                                                                      or "?"),
                                     today, "", r["ours"], b["mat"])
                n += 1
    return back("/admin/cricket/golden", "Accepted %d suggestion(s) that equal our figures." % n)


@router.post("/golden/explain-coverage")
async def golden_explain_coverage(request: Request, admin: str = Depends(get_current_admin)):
    """Careers that start before Cricsheet is dense: take Wikipedia's figure as the reference
    and record why ours is lower, for every such row without a reference yet."""
    same_origin(request)
    view = runner.golden_view()
    today = date.today().isoformat()
    rows = golden.coverage_explanations(view["blocks"])
    for b, r, why in rows:
        store.save_reference((b["id"], b["scope"], r["metric"]), r["suggestion"],
                             "Wikipedia infobox, as of %s" % (r["suggestion_as_of"] or "?"),
                             today, why, r["ours"], b["mat"])
    blocks = len({(b["id"], b["scope"]) for b, _, _ in rows})
    return back("/admin/cricket/golden", "Explained %d row(s) in %d coverage-gap block(s)."
                % (len(rows), blocks))


@router.post("/golden/check")
async def golden_check(request: Request, admin: str = Depends(get_current_admin)):
    same_origin(request)
    s = runner.run_check()
    msg = s.get("skipped") or "Check done: %s match, %s explained, %s stale, %s DIFF." % (
        s["match"], s["explained"], s["stale"], s["DIFF"])
    return back("/admin/cricket", msg)


@router.get("/golden.csv")
async def golden_csv(admin: str = Depends(get_current_admin)):
    view = runner.golden_view()
    return Response(golden.to_csv(view["blocks"]), media_type="text/csv",
                    headers={"Content-Disposition":
                             'attachment; filename="golden-figures.csv"'})
