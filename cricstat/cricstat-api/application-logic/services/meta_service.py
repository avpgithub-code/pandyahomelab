"""Health, status, scopes, competitions, metrics and search (F5 §3 "Meta and status")."""
import json
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from application_logic.services.common import gender, team_slugs
from application_logic.services.slugs import GENDER, player_slug
from db_logic.repository import meta_repo
from db_logic.repository.db import ServingDB
from shared.exceptions import BadFilter

SCOPE_LABELS = {"ALL": "All (internationals + featured leagues)", "LEAGUES": "Leagues",
                "TEST": "Test", "ODI": "ODI", "T20I": "T20I", "T20I_OTHER": "T20I (other)",
                "OD_INTL_OTHER": "One-day international (other)",
                "MD_INTL_OTHER": "Multi-day international (other)", "T20_LEAGUE": "T20 leagues",
                "HUNDRED": "The Hundred", "LIST_A": "List A", "FIRST_CLASS": "First-class"}
SEARCH_TYPES = ("player", "team", "competition")


def health(db: ServingDB) -> dict:
    b = meta_repo.latest_build(db)
    return {"status": "ok", "build_id": b["build_id"] if b else None,
            "data_as_of": b["data_as_of"] if b else None}


SOURCE_STALE_DAYS = 14


def source_freshness(runs: list, now: Optional[datetime] = None) -> dict:
    """When Cricsheet last changed its files (from the downloads' Last-Modified, recorded by each
    ingest run) and when we last checked. Lets pages say "the source hasn't published" instead of
    looking stale, and lets the admin page warn when the source goes quiet for long."""
    now = now or datetime.now(timezone.utc)
    ok = [r for r in runs if r["mode"] in ("recent", "full") and r["status"] == "success"]
    checked = ok[0]["finished_at"] if ok else None
    updated = max((r["source_last_modified"] for r in ok if r.get("source_last_modified")),
                  default=None)
    days = None
    if updated:
        then = datetime.strptime(updated, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        days = (now - then).days
    return {"name": "Cricsheet", "last_updated": updated, "last_checked": checked,
            "days_since_update": days,
            "stale": days is not None and days > SOURCE_STALE_DAYS,
            "stale_after_days": SOURCE_STALE_DAYS}


def status(db: ServingDB, raw_db: str) -> Tuple[dict, dict]:
    b = meta_repo.latest_build(db) or {}
    notes = json.loads(b.get("notes") or "{}")
    runs = meta_repo.ingest_runs(raw_db, limit=20)
    data = {"build": {k: b.get(k) for k in ("build_id", "built_at", "mode", "matches",
                                            "deliveries", "data_as_of")},
            "warnings": notes.get("warnings", []),
            "source": source_freshness(runs),
            "builds": meta_repo.recent_builds(db),
            "ingest_runs": runs[:5],
            "counts": meta_repo.counts(db)}
    return data, {"source.last_updated": "When Cricsheet last changed its download files"
                                         " (HTTP Last-Modified), recorded by our daily check."}


def scopes(db: ServingDB) -> Tuple[List[dict], dict]:
    s = db.scopes()
    out = [{"scope": "ALL", "label": SCOPE_LABELS["ALL"], "kind": "group"},
           {"scope": "LEAGUES", "label": SCOPE_LABELS["LEAGUES"], "kind": "group"}]
    order = ["TEST", "ODI", "T20I"] + sorted(k for k in s.formats if k not in ("TEST", "ODI",
                                                                                "T20I"))
    for k in order:
        f = s.formats[k]
        out.append({"scope": k, "label": SCOPE_LABELS.get(k, k), "kind": "format",
                    "format_family": f["format_family"], "level": f["level"],
                    "in_v1_tabs": k in ("TEST", "ODI", "T20I")})
    for slug, c in sorted(s.featured.items()):
        out.append({"scope": slug, "label": c["event_name"], "kind": "league",
                    "gender": c["gender"]})
    return out, {}


def competitions(db: ServingDB, featured: Optional[bool]) -> Tuple[List[dict], dict]:
    rows = meta_repo.competitions(db, featured)
    for r in rows:
        r["is_featured"] = bool(r["is_featured"])
        r["seasons"] = sorted(set((r.pop("seasons") or "").split(",")) - {""})
    return rows, {}


def metric_list(db: ServingDB) -> Tuple[List[dict], dict]:
    return [{"object": r["object_name"], "column": r["column_name"] or None,
             "description": r["description"]} for r in meta_repo.catalog(db)], {}


def search(db: ServingDB, q: Optional[str], kind: Optional[str], g: Optional[str],
           limit: Optional[int]) -> Tuple[dict, dict]:
    q = (q or "").strip()
    if len(q) < 2:
        raise BadFilter("q needs at least 2 characters")
    if len(q) > 60:
        raise BadFilter("q is at most 60 characters")
    kinds = SEARCH_TYPES if not kind else tuple(kind.split("|"))
    if any(k not in SEARCH_TYPES for k in kinds):
        raise BadFilter("type is player, team or competition (or several joined with |)")
    g = gender(g)
    limit = min(max(limit or 10, 1), 50)
    out = {}
    if "player" in kinds:
        out["players"] = [
            {"player_id": r["player_id"], "name": r["name"],
             "slug": player_slug(r["name"], r["player_id"]),
             "match": ["exact", "starts with", "word starts with", "contains"][r["rank"]],
             "gender": r["gender"], "gender_label": GENDER.get(r["gender"]),
             "main_team": r["main_team"], "matches": r["matches"],
             "years": "%s–%s" % ((r["first_date"] or "")[:4], (r["last_date"] or "")[:4])}
            for r in meta_repo.search_players(db, q, g, limit)]
    if "team" in kinds:
        ql = q.lower()
        teams = [t for t in team_slugs(db).by_slug.values()
                 if ql in t["name"].lower() and t["matches"] and (not g or t["gender"] == g)]
        teams.sort(key=lambda t: (not t["name"].lower().startswith(ql),
                                  t["team_type"] != "international", -t["matches"]))
        out["teams"] = [{"slug": t["slug"], "name": t["name"], "gender": t["gender"],
                         "gender_label": GENDER.get(t["gender"]), "team_type": t["team_type"],
                         "matches": t["matches"]} for t in teams[:limit]]
    if "competition" in kinds:
        out["competitions"] = [dict(r, is_featured=bool(r["is_featured"]))
                               for r in meta_repo.search_competitions(db, q, limit)]
    return out, {}
