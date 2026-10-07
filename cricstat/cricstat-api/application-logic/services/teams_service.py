"""Teams: identity, record, results, head to head, home/away, years, top players (F5 §3)."""
from typing import List, Optional, Tuple

from application_logic.services import metrics
from application_logic.services.common import catalog_defs, dates, gender, page, team_slugs
from application_logic.services.matches_service import score_line
from application_logic.services.slugs import GENDER, player_slug
from db_logic.repository import matches_repo, teams_repo
from db_logic.repository.db import ServingDB
from shared.exceptions import BadFilter, NotFound

TYPES = ("international", "club")
METRICS = ("runs", "wickets")
_RESULT = ("won", "lost", "tied", "drawn", "no_result")


def _team(db: ServingDB, slug: str) -> dict:
    t = team_slugs(db).get(slug)
    if t is None:
        raise NotFound("no team with slug %r" % slug)
    return t


def _ref(t: dict) -> dict:
    return {"slug": t["slug"], "name": t["name"], "gender": t["gender"],
            "gender_label": GENDER.get(t["gender"]), "team_type": t["team_type"]}


def _scope(db: ServingDB, scope: Optional[str]) -> Optional[str]:
    return db.scopes().check(scope) if scope else None


def _with_pct(row: dict) -> dict:
    return dict(row, win_pct=metrics.win_pct(row["won"], row["matches"], row["no_result"]))


def list_teams(db: ServingDB, g: Optional[str], team_type: Optional[str]
               ) -> Tuple[List[dict], dict]:
    g = gender(g)
    if team_type and team_type not in TYPES:
        raise BadFilter("type is international or club")
    out = [dict(_ref(t), matches=t["matches"], first_date=t["first_date"],
                last_date=t["last_date"])
           for t in team_slugs(db).by_slug.values()
           if t["matches"] and (not g or t["gender"] == g)
           and (not team_type or t["team_type"] == team_type)]
    return sorted(out, key=lambda t: -t["matches"]), {}


def team(db: ServingDB, slug: str) -> Tuple[dict, dict]:
    t = _team(db, slug)
    formats = [{"format": r["format_key"], "matches": r["matches"]}
               for r in teams_repo.record(db, t["team_key"], None)]
    data = dict(_ref(t), matches=t["matches"], first_date=t["first_date"],
                last_date=t["last_date"], formats=formats,
                ratings=[],
                notes={"ratings": "Team ratings arrive with the WC 2027 predictor (P1)."})
    return data, {}


def record(db: ServingDB, slug: str, scope: Optional[str], date_from: Optional[str] = None,
           date_to: Optional[str] = None) -> Tuple[List[dict], dict]:
    """By format (all time, from the F4 view), or for one scope and/or a date window."""
    t = _team(db, slug)
    scope = _scope(db, scope)
    d_from, d_to = dates(date_from, date_to)
    if (d_from or d_to) and not scope:
        raise BadFilter("a date window needs a scope (e.g. scope=ODI)")
    rows = teams_repo.record(db, t["team_key"], scope, d_from, d_to)
    if scope:
        rows = [_with_pct(dict(r, format=scope)) for r in rows if r["matches"]]
    else:
        rows = [{"format": r["format_key"], **{k: r[k] for k in ("matches",) + _RESULT},
                 "win_pct": r["win_pct"]} for r in rows]
    return rows, catalog_defs(db, [("v_team_record", "matches"), ("v_team_record", "tied"),
                                   ("v_team_record", "win_pct")])


def results(db: ServingDB, slug: str, scope: Optional[str], date_from: Optional[str],
            date_to: Optional[str], limit: Optional[int], offset: Optional[int]
            ) -> Tuple[List[dict], dict, bool]:
    t = _team(db, slug)
    scope = _scope(db, scope)
    d_from, d_to = dates(date_from, date_to)
    limit, offset = page(limit, offset)
    rows = teams_repo.results(db, t["team_key"], scope, d_from, d_to, limit + 1, offset)
    slugs = team_slugs(db)
    scores = matches_repo.innings_scores(db, [r["match_id"] for r in rows[:limit]])
    out = [{"match_id": r["match_id"], "date": r["start_date"], "format": r["format_key"],
            "competition": r["competition"],
            "opponent": {"name": r["opponent"],
                         "slug": slugs.find(r["opponent"], r["gender"], r["team_type"])},
            "outcome": r["outcome"], "margin_runs": r["margin_runs"],
            "margin_wickets": r["margin_wickets"], "margin_innings": r["win_by_innings"],
            "method": r["method"], "decided_by": r["decided_by"], "winner": r["winner"],
            "venue": r["venue"], "city": r["city"], "home_away": r["home_away"],
            "scores": [{"team": slugs.slug(i["team_key"]), "score": score_line(i),
                        "super_over": bool(i["is_super_over"])}
                       for i in scores.get(r["match_id"], [])]}
           for r in rows[:limit]]
    return out, {}, len(rows) > limit


def head_to_head(db: ServingDB, slug: str, scope: Optional[str], opponent: Optional[str]
                 ) -> Tuple[List[dict], dict]:
    t = _team(db, slug)
    scope = _scope(db, scope)
    opp_key = _team(db, opponent)["team_key"] if opponent else None
    slugs = team_slugs(db)
    out = []
    for r in teams_repo.head_to_head(db, t["team_key"], scope, opp_key):
        row = _with_pct({k: r[k] for k in ("matches",) + _RESULT})
        row.update(format=r["format_key"], last_played=r["last_played"],
                   last_outcome=r["last_outcome"],
                   opponent={"name": r["opponent"], "slug": slugs.slug(r["opponent_key"])})
        out.append(row)
    return out, catalog_defs(db, [("v_head_to_head", "win_pct")])


def home_away(db: ServingDB, slug: str, scope: Optional[str]) -> Tuple[List[dict], dict]:
    t = _team(db, slug)
    if t["team_type"] != "international":
        raise BadFilter("home / away is only defined for international teams (F4 §2)")
    rows = [_with_pct(r) for r in teams_repo.home_away(db, t["team_key"], _scope(db, scope))]
    return rows, catalog_defs(db, [("team_results", "home_away")])


def years(db: ServingDB, slug: str, scope: Optional[str]) -> Tuple[List[dict], dict]:
    t = _team(db, slug)
    rows = [_with_pct(r) for r in teams_repo.years(db, t["team_key"], _scope(db, scope))]
    return rows, {"win_pct": metrics.DEFINITIONS["win_pct"]}


def top_players(db: ServingDB, slug: str, scope: Optional[str], metric: str,
                date_from: Optional[str], date_to: Optional[str], limit: Optional[int]
                ) -> Tuple[List[dict], dict]:
    t = _team(db, slug)
    if metric not in METRICS:
        raise BadFilter("metric must be runs or wickets")
    d_from, d_to = dates(date_from, date_to)
    limit, _ = page(limit if limit is not None else 10, 0)
    out = []
    for r in teams_repo.top_players(db, t["team_key"], _scope(db, scope), metric, d_from, d_to,
                                    limit):
        row = {"player_id": r["player_id"], "name": r["name"],
               "slug": player_slug(r["name"], r["player_id"]), "matches": r["matches"],
               "innings": r["innings"]}
        if metric == "runs":
            row.update(runs=r["runs"], average=metrics.batting_average(r["runs"], r["outs"]),
                       strike_rate=metrics.strike_rate(r["runs"], r["balls_faced"]))
        else:
            row.update(wickets=r["wickets"],
                       average=metrics.bowling_average(r["runs_conceded"], r["wickets"]),
                       economy=metrics.economy(r["runs_conceded"], r["legal_balls"]))
        out.append(row)
    defs = {"scope_note": "Counts only what each player did while playing for this team."}
    keys = ("average", "strike_rate") if metric == "runs" else ("bowling_average", "economy")
    defs.update({k: metrics.DEFINITIONS[k] for k in keys})
    return out, defs
