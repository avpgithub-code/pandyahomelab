"""Verify References (manual) and the weekly golden check (scheduled), P0.3b.

Verify: fetch Wikipedia suggestions for the fixed golden selection. Only one run at a time: an
in-process lock plus a 'running' row in cricstat.golden_run (the button is disabled meanwhile).
Weekly check: recompute every row's status against cricstat-api's current figures and record a
summary (DIFF rows listed); the DSM weekly report email includes it.
"""
import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.cricstat import api_client, golden, store, wiki

logger = logging.getLogger("admin-portal.cricstat")
_lock = threading.Lock()
CHECK_EVERY = timedelta(days=7)


def golden_view() -> dict:
    """Our figures merged with references and suggestions, plus counts."""
    data = api_client.get("/v1/admin/golden")
    blocks = golden.merge(data["blocks"], store.references(), store.suggestions(),
                          data["window_to"])
    return dict(data, blocks=blocks, summary=golden.summary(blocks))


def start_verify() -> Optional[int]:
    """Start a Verify References run in a background thread. None if one is already running."""
    if not _lock.acquire(blocking=False):
        return None
    try:
        run_id = store.start_run("verify")
    except Exception:
        _lock.release()
        raise
    if run_id is None:
        _lock.release()
        return None
    threading.Thread(target=_verify, args=(run_id,), daemon=True, name="verify").start()
    return run_id


def _verify(run_id: int) -> None:
    try:
        blocks = api_client.get("/v1/admin/golden", timeout=60)["blocks"]
        players = {}
        for b in blocks:
            if b["kind"] == "player":
                players.setdefault(b["id"], {"id": b["id"], "name": b["name"],
                                             "cricinfo_ids": b.get("cricinfo_ids", [])})
        results = wiki.fetch_suggestions(list(players.values()), log=logger)
        rows = golden.suggestion_rows(results, blocks)
        store.replace_suggestions(rows)
        merged = golden.merge(blocks, store.references(), store.suggestions())
        s = golden.summary(merged)
        summary = {"players": len(players),
                   "articles": sum(1 for r in results.values() if "scopes" in r),
                   "suggestions": len(rows), "agree_with_ours": s["suggestion_agrees"],
                   "not_found": sorted(players[i]["name"] for i, r in results.items()
                                       if "error" in r)}
        store.finish_run(run_id, "success", summary)
        logger.info("verify run %d: %s", run_id, summary)
    except Exception as exc:
        logger.exception("verify run %d failed", run_id)
        store.finish_run(run_id, "error", error="%s: %s" % (type(exc).__name__, exc))
    finally:
        _lock.release()


def run_check() -> dict:
    run_id = store.start_run("check")
    if run_id is None:
        return {"skipped": "a check is already running"}
    try:
        view = golden_view()
        diffs = ["%s %s %s: ours %s, reference %s" % (b["name"], b["scope"], r["metric"],
                                                       r["ours"], r["reference"])
                 for b in view["blocks"] for r in b["rows"] if r["status"] == "DIFF"]
        summary = dict(view["summary"], window_to=view["window_to"], diffs=diffs[:50])
        store.finish_run(run_id, "success", summary)
        return summary
    except Exception as exc:
        store.finish_run(run_id, "error", error="%s: %s" % (type(exc).__name__, exc))
        raise


async def weekly_check_loop() -> None:
    """Every hour, run the check if the last successful one is older than a week."""
    loop = asyncio.get_running_loop()
    while True:
        try:
            last = await loop.run_in_executor(None, store.last_run, "check")
            due = (last is None or last["status"] != "success"
                   or datetime.now(timezone.utc) - last["started_at"] > CHECK_EVERY)
            if due:
                summary = await loop.run_in_executor(None, run_check)
                logger.info("weekly golden check: %s", {k: v for k, v in summary.items()
                                                       if k != "diffs"})
        except Exception as exc:
            logger.warning("weekly golden check failed: %s", exc)
        await asyncio.sleep(3600)


def report_lines() -> list:
    """Cricket section for the weekly report email (app.weekly_report)."""
    out = ["", "CRICSTAT (pandyahomelab.com/admin/cricket)"]
    try:
        jobs = api_client.get("/v1/admin/jobs")
    except api_client.CricstatUnavailable as exc:
        return out + ["  cricstat-api unreachable: %s" % exc]
    for j in jobs["jobs"]:
        lr = j["last_run"] or {}
        flag = "ok " if j["healthy"] else ("OVERDUE" if j["overdue"] else "FAILED")
        out.append("  %-8s %-16s last %s" % (flag, j["name"], (lr.get("started_at") or "never")
                                              .replace("T", " ")[:16]))
    b = jobs["builds"][0] if jobs["builds"] else {}
    if b:
        out.append("  Data as of %s · build %s (%s)" % (b["data_as_of"], b["build_id"], b["mode"]))
        for w in b["notes"].get("warnings", []):
            out.append("  warning: %s" % w)
    check = store.last_run("check")
    if check and check["summary"]:
        s = check["summary"]
        out.append("  Golden figures: %s with a reference — %s match, %s explained, %s stale,"
                   " %s DIFF" % (s["with_reference"], s["match"], s["explained"], s["stale"],
                                 s["DIFF"]))
        for d in s.get("diffs", [])[:10]:
            out.append("    DIFF %s" % d)
    return out
