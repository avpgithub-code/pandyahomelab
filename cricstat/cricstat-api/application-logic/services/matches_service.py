"""Match list with scores and simple leaderboards (F5 §3). Ratios from metrics.py (F4 R17)."""
from typing import List, Optional, Tuple

from application_logic.services import metrics
from application_logic.services.common import dates, gender, page, team_slugs
from application_logic.services.slugs import player_slug
from db_logic.repository import matches_repo
from db_logic.repository.db import ServingDB
from shared.exceptions import BadFilter, NotFound

LEADER_METRICS = {"batting": ("runs",), "bowling": ("wickets",)}


def score_line(inn: dict) -> str:
    """"287/6 (50 ov)", "350/8d", "142" (all out); overs in that match's balls per over."""
    bpo = inn.get("balls_per_over") or 6
    s = str(inn["runs"])
    if inn["wickets"] < 10 or inn["declared"]:
        s += "/%d" % inn["wickets"]
    if inn["declared"]:
        s += "d"
    balls = inn["legal_balls"] or 0
    s += " (%d.%d ov)" % (balls // bpo, balls % bpo) if balls % bpo else " (%d ov)" % (balls // bpo)
    return s


def with_scores(db: ServingDB, rows: List[dict]) -> List[dict]:
    """Shape match rows: both teams with slugs and their innings scores (super overs apart)."""
    slugs = team_slugs(db)
    scores = matches_repo.innings_scores(db, [r["match_id"] for r in rows])
    out = []
    for r in rows:
        inns = scores.get(r["match_id"], [])
        teams = []
        for key in (r["team1_key"], r["team2_key"]):
            t = slugs.get(slugs.slug(key)) or {}
            mine = [i for i in inns if i["team_key"] == key and not i["is_super_over"]]
            teams.append({"name": t.get("name"), "slug": slugs.slug(key),
                          "won": r["winner"] == t.get("name") and r["result"] == "win",
                          "innings": [score_line(i) for i in mine]})
        margin = None
        if r["result"] == "win":
            if r["win_by_innings"]:
                margin = "an innings and %s runs" % r["win_by_runs"]
            elif r["win_by_runs"] is not None:
                margin = "%s runs" % r["win_by_runs"]
            elif r["win_by_wickets"] is not None:
                margin = "%s wickets" % r["win_by_wickets"]
        out.append({"match_id": r["match_id"], "date": r["start_date"], "end_date": r["end_date"],
                    "format": r["format_key"], "gender": r["gender"],
                    "competition": r["competition"], "competition_slug": r["competition_slug"],
                    "venue": r["venue"], "city": r["city"], "result": r["result"],
                    "winner": r["winner"], "margin": margin, "method": r["method"],
                    "decided_by": r["decided_by"], "teams": teams,
                    "super_over": any(i["is_super_over"] for i in inns)})
    return out


def list_matches(db: ServingDB, scope: Optional[str], g: Optional[str], team: Optional[str],
                 date_from: Optional[str], date_to: Optional[str], limit: Optional[int],
                 offset: Optional[int]) -> Tuple[List[dict], dict, bool]:
    scope = db.scopes().check(scope) if scope else None
    g = gender(g)
    team_key = None
    if team:
        t = team_slugs(db).get(team)
        if t is None:
            raise NotFound("no team with slug %r" % team)
        team_key = t["team_key"]
    d_from, d_to = dates(date_from, date_to)
    limit, offset = page(limit, offset)
    rows = matches_repo.matches(db, scope, g, team_key, d_from, d_to, limit + 1, offset)
    return with_scores(db, rows[:limit]), {}, len(rows) > limit


def leaderboard(db: ServingDB, kind: str, metric: str, scope: Optional[str], g: Optional[str],
                date_from: Optional[str], date_to: Optional[str], limit: Optional[int]
                ) -> Tuple[List[dict], dict]:
    if metric not in LEADER_METRICS[kind]:
        raise BadFilter("metric for %s is %s for now" % (kind, " or ".join(LEADER_METRICS[kind])))
    scope = db.scopes().check(scope) if scope else None
    g = gender(g)
    d_from, d_to = dates(date_from, date_to)
    limit, _ = page(limit if limit is not None else 10, 0)
    out = []
    for r in matches_repo.leaders(db, kind, scope, g, d_from, d_to, limit):
        row = {"player_id": r["player_id"], "name": r["name"], "team": r["team"],
               "slug": player_slug(r["name"], r["player_id"]), "matches": r["matches"],
               "innings": r["innings"]}
        if kind == "batting":
            row.update(runs=r["runs"], best=r["best"],
                       average=metrics.batting_average(r["runs"], r["outs"]),
                       strike_rate=metrics.strike_rate(r["runs"], r["balls_faced"]))
        else:
            row.update(wickets=r["wickets"],
                       average=metrics.bowling_average(r["runs_conceded"], r["wickets"]),
                       economy=metrics.economy(r["runs_conceded"], r["legal_balls"]))
        out.append(row)
    keys = ("average", "strike_rate") if kind == "batting" else ("bowling_average", "economy")
    return out, {k: metrics.DEFINITIONS[k] for k in keys}
