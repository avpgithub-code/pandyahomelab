"""Players: profile, career, years, phases, splits, innings (F5 §3 "Players")."""
from typing import Dict, List, Optional, Tuple

from application_logic.services import metrics
from application_logic.services.common import catalog_defs, dates, page, team_slugs
from application_logic.services.slugs import GENDER, full_name, player_slug
from db_logic.repository import pages_repo, players_repo
from db_logic.repository.db import ServingDB
from shared.exceptions import BadFilter, Incompatible, NotFound

ROLE_RULE = ("Derived from the ALL scope (or the most-played one): wicketkeeper when stumpings"
             " ≥ 1 per 20 matches; all-rounder when bowling in ≥ half the matches and averaging"
             " ≥ 20 with the bat; bowler when bowling in ≥ half the matches; otherwise batter.")
SPLITS = ("opponent", "venue", "season")
PHOTO_PATH = "/cricket/photos/"      # served by Nginx from data/photos (read-only)


def _player(db: ServingDB, player_id: str) -> dict:
    p = players_repo.identity(db, player_id)
    if p is None:
        raise NotFound("no player with id %r" % player_id)
    return p


def photo(p: dict) -> Optional[dict]:
    """The self-hosted Commons thumbnail and the credit its licence needs (P0.5), or None."""
    if not p.get("photo_file"):
        return None
    return {"url": PHOTO_PATH + p["photo_file"], "width": p["photo_width"],
            "height": p["photo_height"], "licence": p["photo_licence"],
            "licence_url": p["photo_licence_url"], "author": p["photo_author"],
            "source_url": p["photo_source_url"], "source": "Wikimedia Commons"}


def _ref(p: dict) -> dict:
    return {"player_id": p["player_id"], "name": p["name"],
            "slug": player_slug(p["name"], p["player_id"])}


def derive_role(c: Dict[str, Optional[dict]]) -> Optional[str]:
    m = (c.get("matches") or {}).get("matches") or 0
    if not m:
        return None
    bat, bowl, fld = c.get("batting") or {}, c.get("bowling") or {}, c.get("fielding") or {}
    if (fld.get("stumpings") or 0) * 20 >= m:
        return "wicketkeeper"
    bowls = (bowl.get("innings") or 0) * 2 >= m
    if bowls and (bat.get("average") or 0) >= 20:
        return "all-rounder"
    return "bowler" if bowls else "batter"


def profile(db: ServingDB, player_id: str) -> Tuple[dict, dict]:
    p = _player(db, player_id)
    slugs = team_slugs(db)
    teams = []
    for t in players_repo.teams(db, p["player_key"]):
        teams.append(dict(slug=slugs.find(t["name"], t["gender"], t["team_type"]),
                          name=t["name"], gender=t["gender"], team_type=t["team_type"],
                          matches=t["matches"], first_date=t["first_date"],
                          last_date=t["last_date"]))
    scopes = players_repo.scopes_played(db, p["player_key"])
    gender = scopes[0]["gender"] if scopes else None
    basis = next((s["scope"] for s in scopes if s["scope"] == "ALL"),
                 scopes[0]["scope"] if scopes else None)
    role = derive_role(players_repo.career(db, p["player_key"], basis)) if basis else None
    main = next((t for t in teams if t["team_type"] == "international"),
                teams[0] if teams else None)
    variants = pages_repo.name_variants(db, p["player_key"])
    data = dict(_ref(p), full_name=full_name(p["name"], variants, p["wd_name"]),
                unique_name=p["unique_name"], gender=gender,
                gender_label=GENDER.get(gender), main_team=main, role=role,
                bio={"wikidata_qid": p["wikidata_qid"], "date_of_birth": p["date_of_birth"],
                     "birthplace": p["birthplace"], "country_for_sport": p["country_for_sport"],
                     "source": "Wikidata (CC0)" if p["wikidata_qid"] else None},
                photo=photo(p),
                teams=teams,
                scopes=[{"scope": s["scope"], "matches": s["matches"],
                         "first_date": s["first_date"], "last_date": s["last_date"]}
                        for s in scopes],
                first_date=min((s["first_date"] for s in scopes), default=None),
                last_date=max((s["last_date"] for s in scopes), default=None))
    return data, {"role": ROLE_RULE}


def career(db: ServingDB, player_id: str, scope: str) -> Tuple[dict, dict]:
    p = _player(db, player_id)
    scope = db.scopes().check(scope)
    c = players_repo.career(db, p["player_key"], scope)
    bat, bowl, fld = c["batting"], c["bowling"], c["fielding"]
    data = {
        "player": dict(_ref(p), gender=(c["matches"] or {}).get("gender")),
        "scope": scope,
        "matches": (c["matches"] or {}).get("matches", 0),
        "first_date": (c["matches"] or {}).get("first_date"),
        "last_date": (c["matches"] or {}).get("last_date"),
        "batting": _bat(bat),
        "bowling": _bowl(bowl),
        "fielding": None if not fld else {
            "catches": fld["catches"], "stumpings": fld["stumpings"],
            "run_out_involvements": fld["run_outs"], "dismissals": fld["dismissals"],
            "notes": {"run_out_involvements": "Not an official statistic: counts each fielder"
                                              " listed in a run-out, so shared run-outs credit"
                                              " both."}},
    }
    defs = catalog_defs(db, [("v_player_batting", "average"), ("v_player_batting", "strike_rate"),
                             ("v_player_batting", "balls_faced"), ("v_player_bowling", "economy"),
                             ("v_player_bowling", "average"), ("v_player_bowling", "strike_rate"),
                             ("v_player_bowling", "wickets"), ("v_player_bowling", "maidens"),
                             ("v_player_fielding", "run_outs")])
    return data, defs


def _bat(b: Optional[dict]) -> Optional[dict]:
    if not b:
        return None
    out = {k: b[k] for k in ("innings", "not_outs", "runs", "balls_faced", "high_score", "average",
                             "strike_rate", "hundreds", "fifties", "ducks", "fours", "sixes")}
    out["high_score_not_out"] = bool(b["high_score_not_out"])
    return out


def _bowl(b: Optional[dict]) -> Optional[dict]:
    if not b:
        return None
    out = {k: b[k] for k in ("innings", "legal_balls", "overs_display", "maidens", "runs_conceded",
                             "wickets", "average", "economy", "strike_rate", "four_wkt_hauls",
                             "five_wkt_hauls")}
    out["best"] = {"wickets": b["best_bowling_wkts"], "runs": b["best_bowling_runs"]}
    return out


def years(db: ServingDB, player_id: str, scope: str) -> Tuple[List[dict], dict]:
    p = _player(db, player_id)
    scope = db.scopes().check(scope)
    rows = []
    for y in players_repo.years(db, p["player_key"], scope):
        outs = (y["bat_innings"] or 0) - (y["not_outs"] or 0)
        rows.append(dict(y, average=metrics.batting_average(y["runs"], outs),
                         strike_rate=metrics.strike_rate(y["runs"], y["balls_faced"]),
                         bowling_average=metrics.bowling_average(y["runs_conceded"], y["wickets"]),
                         economy=metrics.economy(y["runs_conceded"], y["legal_balls"])))
    return rows, _defs("average", "strike_rate", "bowling_average", "economy")


def phases(db: ServingDB, player_id: str, scope: str) -> Tuple[List[dict], dict]:
    p = _player(db, player_id)
    scopes = db.scopes()
    scope = scopes.check(scope)
    if scope in ("ALL", "LEAGUES") or scopes.family(scope) == "multi_day":
        raise Incompatible("phases need one limited-overs format or league (e.g. T20I, ODI, ipl);"
                           " %s mixes or has no phases" % scope)
    rows = []
    for r in players_repo.phases(db, p["player_key"], scope):
        rows.append({"format_family": r["format_family"], "phase": r["phase"],
                     "label": r["label"], "bat_runs": r["bat_runs"], "bat_balls": r["bat_balls"],
                     "bat_outs": r["bat_outs"],
                     "bat_strike_rate": metrics.strike_rate(r["bat_runs"], r["bat_balls"]),
                     "bowl_balls": r["bowl_balls"], "bowl_runs": r["bowl_runs"],
                     "bowl_wkts": r["bowl_wkts"],
                     "bowl_economy": metrics.economy(r["bowl_runs"], r["bowl_balls"])})
    defs = _defs("strike_rate", "economy")
    defs.update(catalog_defs(db, [("v_player_phase", "")]))
    return rows, defs


def splits(db: ServingDB, player_id: str, scope: str, by: str) -> Tuple[dict, dict]:
    p = _player(db, player_id)
    if by not in SPLITS:
        raise BadFilter("by must be one of %s" % ", ".join(SPLITS))
    scope = db.scopes().check(scope)
    raw = players_repo.splits(db, p["player_key"], scope, by)
    slugs = team_slugs(db)
    out = {}
    for kind, rows in raw.items():
        shaped = []
        for r in rows:
            row = dict(r)
            if by == "opponent":
                row["slug"] = slugs.find(r["label"], r["gender"], r["team_type"])
            if kind == "batting":
                row["average"] = metrics.batting_average(r["runs"], r["outs"])
                row["strike_rate"] = metrics.strike_rate(r["runs"], r["balls_faced"])
            else:
                row["average"] = metrics.bowling_average(r["runs_conceded"], r["wickets"])
                row["economy"] = metrics.economy(r["runs_conceded"], r["legal_balls"])
            shaped.append(row)
        key = "runs" if kind == "batting" else "wickets"
        out[kind] = sorted(shaped, key=lambda r: (-(r[key] or 0), str(r["label"])))
    return {"by": by, "scope": scope, **out}, _defs("average", "strike_rate", "bowling_average",
                                                     "economy")


def innings(db: ServingDB, player_id: str, scope: str, date_from: Optional[str],
            date_to: Optional[str], limit: Optional[int], offset: Optional[int]
            ) -> Tuple[List[dict], dict, bool]:
    p = _player(db, player_id)
    scope = db.scopes().check(scope)
    d_from, d_to = dates(date_from, date_to)
    limit, offset = page(limit, offset)
    rows = players_repo.innings(db, p["player_key"], scope, d_from, d_to, limit + 1, offset)
    more = len(rows) > limit
    rows = rows[:limit]
    detail = players_repo.innings_detail(db, p["player_key"], [r["match_id"] for r in rows])
    slugs = team_slugs(db)
    out = []
    for r in rows:
        out.append({"match_id": r["match_id"], "date": r["start_date"], "format": r["format_key"],
                    "team": slugs.slug(r["team_key"]),
                    "opponent": {"name": r["opponent"],
                                 "slug": slugs.find(r["opponent"], r["gender"], r["team_type"])},
                    "venue": r["venue"], "city": r["city"], "result": r["result"],
                    "winner": r["winner"],
                    "batting": [b for b in detail["batting"] if b["match_id"] == r["match_id"]],
                    "bowling": [b for b in detail["bowling"] if b["match_id"] == r["match_id"]]})
    for row in out:
        for b in row["batting"] + row["bowling"]:
            b.pop("match_id")
    return out, {}, more


def _defs(*keys: str) -> dict:
    return {k: metrics.DEFINITIONS[k] for k in keys}
