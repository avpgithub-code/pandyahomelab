"""Internal admin views (P0.3b): scheduled jobs, data overview, golden figures.

Served under /v1/admin/ for the admin portal only; Nginx keeps /cricket/api/v1/admin/ off the
public site. The DSM schedule itself is not visible from a container, so JOBS states it (keep in
step with cricstat/CLAUDE.md "DSM scheduled tasks"); last runs come from the run logs.
"""
import csv
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from application_logic.services import golden, meta_service
from application_logic.services.common import team_slugs
from application_logic.services.metrics import win_pct
from db_logic.repository import meta_repo, ops_repo, players_repo, teams_repo
from db_logic.repository.db import ServingDB
from shared.exceptions import NoData

# NAS local time is a fixed UTC offset (America/Bogota, no DST) — configurable.
JOBS = [
    {"key": "cd_pull", "name": "CD pull", "schedule": "Daily 05:15", "every": "day",
     "at": (5, 15), "command": "sh deployment/cricstat/cd-pull.sh"},
    {"key": "daily", "name": "Daily refresh", "schedule": "Daily 05:30", "every": "day",
     "at": (5, 30), "command": "pipeline recent && build"},
    {"key": "register", "name": "Weekly register", "schedule": "Sunday 06:00", "every": "week",
     "weekday": 6, "at": (6, 0), "command": "pipeline register && build"},
    {"key": "monthly", "name": "Monthly full", "schedule": "Day 1, 04:00", "every": "month",
     "day": 1, "at": (4, 0), "command": "pipeline full && build --full"},
]
GRACE = {"day": timedelta(hours=26), "week": timedelta(days=7, hours=2),
         "month": timedelta(days=31, hours=2)}
TEAM_FROM = "2016-01-01"
CHAIN_WINDOW = timedelta(hours=2)        # a full build takes ~12 min; register + build < 15 min


def _parse(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def next_run(job: dict, now: datetime, offset_hours: float) -> datetime:
    """Next scheduled time (UTC) for a job defined in NAS local time."""
    tz = timezone(timedelta(hours=offset_hours))
    local = now.astimezone(tz)
    h, m = job["at"]
    cand = local.replace(hour=h, minute=m, second=0, microsecond=0)
    if job["every"] == "day":
        if cand <= local:
            cand += timedelta(days=1)
    elif job["every"] == "week":
        cand += timedelta(days=(job["weekday"] - cand.weekday()) % 7)
        if cand <= local:
            cand += timedelta(days=7)
    else:
        cand = cand.replace(day=job["day"])
        if cand <= local:
            y, mo = (cand.year + 1, 1) if cand.month == 12 else (cand.year, cand.month + 1)
            cand = cand.replace(year=y, month=mo)
    return cand.astimezone(timezone.utc)


def jobs(db: ServingDB, raw_db: str, log_dir: str, offset_hours: float,
         now: Optional[datetime] = None) -> Tuple[dict, dict]:
    now = now or datetime.now(timezone.utc)
    runs = meta_repo.ingest_runs(raw_db, limit=60)
    builds = ops_repo.builds(db)
    for b in builds:
        b["notes"] = json.loads(b["notes"] or "{}")
    cd = ops_repo.cd_pull_runs(log_dir)

    def last(mode):
        return next((r for r in runs if r["mode"] == mode), None)

    def build_after(run):
        """The build the same DSM task ran right after this ingest (`… && build`): the first one
        finishing within CHAIN_WINDOW of the run's end. A later, unrelated build is not it."""
        end = _parse(run.get("finished_at") or run.get("started_at"))
        if end is None:
            return None
        chained = [b for b in builds if _parse(b["built_at"])
                   and end <= _parse(b["built_at"]) <= end + CHAIN_WINDOW]
        return min(chained, key=lambda b: b["built_at"]) if chained else None

    out = []
    for job in JOBS:
        if job["key"] == "cd_pull":
            r = cd[0] if cd else None
            last_run = r and {"started_at": r["at"],
                              "status": "error" if r["failed"] else "success",
                              "detail": r["lines"]}
        else:
            mode = {"daily": "recent", "register": "register", "monthly": "full"}[job["key"]]
            r = last(mode)
            last_run = r and {"started_at": r["started_at"], "finished_at": r["finished_at"],
                              "status": r["status"],
                              "detail": {k: r[k] for k in ("added", "updated", "unchanged",
                                                           "removed", "failed", "active_after")},
                              "build": build_after(r)}
        started = _parse(last_run["started_at"]) if last_run else None
        overdue = started is None or now - started > GRACE[job["every"]]
        healthy = bool(last_run) and last_run["status"] == "success" and not overdue
        out.append(dict({k: job[k] for k in ("key", "name", "schedule", "command")},
                        last_run=last_run, overdue=overdue, healthy=healthy,
                        next_run=next_run(job, now, offset_hours).strftime("%Y-%m-%dT%H:%M:%SZ")))
    data = {"jobs": out, "builds": builds, "ingest_runs": runs[:20], "cd_pull_runs": cd[:10],
            "nas_utc_offset_hours": offset_hours,
            "source": meta_service.source_freshness(runs, now)}
    return data, {"jobs": "Schedules are DSM Task Scheduler tasks in NAS local time; 'overdue' ="
                          " no run within the period plus a grace margin."}


def overview(db: ServingDB, serving_db: str, raw_db: str) -> Tuple[dict, dict]:
    b = meta_repo.latest_build(db) or {}
    notes = json.loads(b.get("notes") or "{}")
    data = {"build": {k: b.get(k) for k in ("build_id", "built_at", "mode", "data_as_of",
                                            "matches", "deliveries")},
            "warnings": notes.get("warnings", []),
            "counts": ops_repo.table_counts(db),
            "files": ops_repo.file_sizes({"serving_db": serving_db, "raw_db": raw_db}),
            "matches_per_year": ops_repo.matches_per_year(db)}
    return data, {}


def read_selection(path: str) -> List[dict]:
    if not os.path.exists(path):
        raise NoData("golden selection not found (%s)" % os.path.basename(path))
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def golden_figures(db: ServingDB, selection_path: str, now: Optional[datetime] = None
                   ) -> Tuple[dict, dict]:
    """Our figures for every selected player/team scope, formatted like a published table,
    with Mat per block (for 'stale' detection), Cricinfo ids (to find Wikipedia pages) and the
    coverage hint. References and decisions live in the admin portal, not here."""
    now = now or datetime.now(timezone.utc)
    selection = read_selection(selection_path)
    build = meta_repo.latest_build(db) or {}
    window_to = build.get("data_as_of") or now.strftime("%Y-%m-%d")
    slugs = team_slugs(db)
    ids = ops_repo.cricinfo_ids(db, [s["id"] for s in selection if s["kind"] == "player"])
    dense: Dict[tuple, Optional[int]] = {}
    blocks, missing = [], []
    for sel in selection:
        for scope in [s.strip() for s in sel["scopes"].split(";") if s.strip()]:
            if sel["kind"] == "team":
                name, gender, team_type = sel["id"].split("|")
                slug = slugs.find(name, gender, team_type)
                t = slugs.get(slug) if slug else None
                rec = teams_repo.record(db, t["team_key"], scope, TEAM_FROM, window_to)[0] \
                    if t else {}
                if rec:
                    rec = dict(rec, win_pct=win_pct(rec["won"], rec["matches"], rec["no_result"]))
                rows, window, note = golden.team_rows(rec), "%s..%s" % (TEAM_FROM, window_to), ""
                extra = {"slug": slug}
                if not rec.get("matches"):
                    missing.append("%s %s" % (sel["name"], scope))
            else:
                p = players_repo.identity(db, sel["id"])
                fig = _player_fig(db, p["player_key"], scope) if p else {}
                if not fig:
                    missing.append("%s %s" % (sel["name"], scope))
                rows, window = golden.player_rows(sel["role"], fig), "career"
                key = (scope, sel["gender"])
                if key not in dense:
                    per_year = ops_repo.scope_matches_per_year(db, scope, sel["gender"])
                    dense[key] = (golden.dense_from(per_year, now.year),
                                  min(per_year) if per_year else None)
                label = "%s %s" % ("women's" if sel["gender"] == "female" else "men's", scope)
                note = golden.coverage_note(fig.get("first_date"), dense[key][0], label,
                                            dense[key][1])
                extra = {"cricinfo_ids": ids.get(sel["id"], [])}
            blocks.append(dict(kind=sel["kind"], name=sel["name"], id=sel["id"],
                               gender=sel["gender"], role=sel["role"], scope=scope, window=window,
                               mat=dict(rows).get("Mat", ""), coverage_note=note,
                               why=sel.get("why", ""),
                               rows=[{"metric": m, "ours": v} for m, v in rows], **extra))
    data = {"window_to": window_to, "team_from": TEAM_FROM, "blocks": blocks, "missing": missing}
    return data, {"status_rules": "match / explained / stale (Mat changed since the check) / DIFF"
                                  " (unexplained difference) — see docs/F4 §3."}


def _player_fig(db: ServingDB, player_key: int, scope: str) -> dict:
    c = players_repo.career(db, player_key, scope)
    fig: Dict[str, object] = {}
    for key, prefix in (("batting", "bat_"), ("bowling", "bowl_"), ("fielding", "fld_")):
        if c[key]:
            fig.update({prefix + k: v for k, v in c[key].items()})
    if c["matches"]:
        fig.update(matches=c["matches"]["matches"], first_date=c["matches"]["first_date"])
    return fig
