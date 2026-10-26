"""Head to Head (docs/h2h-plan.md): two players side by side, the matchup between them in each
direction, and the opponents a player met most (for the picker). Official international formats
only at launch; country head to head reuses the teams endpoints."""
from typing import List, Optional, Tuple

from application_logic.services import metrics, players_service
from application_logic.services.slugs import player_slug
from db_logic.repository import h2h_repo, players_repo
from db_logic.repository.db import ServingDB
from shared.exceptions import BadFilter, Incompatible, NoData, NotFound

SCOPES = ("ODI", "TEST", "T20I")           # ODI first, as everywhere on cricstat
ROLES = ("any", "batter", "bowler")
SMALL_SAMPLE_BALLS = 30                    # below this a matchup is labelled "small sample"

DEFS = {
    "balls": "Balls the batter faced from this bowler (every delivery except wides).",
    "outs": "Times the bowler dismissed the batter (run outs are not the bowler's).",
    "average": "Runs per dismissal = runs ÷ outs.",
    "strike_rate": "Runs × 100 ÷ balls.",
    "dot_pct": "Legal balls with no run off the bat, as a share of balls faced.",
    "small_sample": "Fewer than %d balls between them: too few to read much into."
                    % SMALL_SAMPLE_BALLS,
}


def _ready(db: ServingDB) -> None:
    if not h2h_repo.available(db):
        raise NoData("head-to-head data is not built yet")


def _scope(scope: str) -> str:
    if scope not in SCOPES:
        raise BadFilter("head to head covers %s for now; got %r" % (", ".join(SCOPES), scope))
    return scope


def _player(db: ServingDB, player_id: str) -> dict:
    p = players_repo.identity(db, player_id)
    if p is None:
        raise NotFound("no player with id %r" % player_id)
    return p


def _gender(db: ServingDB, p: dict) -> Optional[str]:
    played = players_repo.scopes_played(db, p["player_key"])
    return played[0]["gender"] if played else None


def shape_matchup(row: Optional[dict], dismissals: List[dict]) -> Optional[dict]:
    """Counts → the matchup block of the API (ratios use the F4 formulas in metrics.py)."""
    if not row or not row["balls"] and not row["outs"]:
        return None
    balls = row["balls"]
    return dict(row,
                average=metrics.batting_average(row["runs"], row["outs"]),
                strike_rate=metrics.strike_rate(row["runs"], balls),
                dot_pct=None if not balls else row["dots"] * 100.0 / balls,
                balls_per_out=None if not row["outs"] else balls / row["outs"],
                small_sample=balls < SMALL_SAMPLE_BALLS,
                dismissals=dismissals)


def _side(db: ServingDB, p: dict, scope: str) -> dict:
    data, _ = players_service.career(db, p["player_id"], scope)
    data["player"]["full_name"] = players_service.display(db, [p["player_id"]]).get(
        p["player_id"], {}).get("full_name", p["name"])
    data["player"]["photo"] = players_service.photo(p)
    return data


def players(db: ServingDB, a_id: str, b_id: str, scope: str) -> Tuple[dict, dict]:
    _ready(db)
    scope = _scope(scope)
    if a_id == b_id:
        raise BadFilter("pick two different players")
    a, b = _player(db, a_id), _player(db, b_id)
    ga, gb = _gender(db, a), _gender(db, b)
    if ga and gb and ga != gb:
        raise Incompatible("head to head compares players of the same gender")

    def block(bat: dict, bowl: dict) -> Optional[dict]:
        row = h2h_repo.matchup(db, scope, bat["player_key"], bowl["player_key"])
        return shape_matchup(row, h2h_repo.outs(db, scope, bat["player_key"], bowl["player_key"])
                             if row else [])

    met = {r["scope"]: r["balls"] for r in h2h_repo.balls_by_scope(db, a["player_key"],
                                                                    b["player_key"])}
    data = {
        "scope": scope,
        "a": _side(db, a, scope),
        "b": _side(db, b, scope),
        "matchup": {"a_batting": block(a, b), "b_batting": block(b, a)},
        "formats": [{"scope": s, "balls_between": met.get(s, 0)} for s in SCOPES],
    }
    return data, DEFS


def opponents(db: ServingDB, player_id: str, scope: str, role: str, limit: Optional[int]
              ) -> Tuple[List[dict], dict]:
    _ready(db)
    scope = _scope(scope)
    if role not in ROLES:
        raise BadFilter("as must be one of %s" % ", ".join(ROLES))
    limit = 10 if limit is None else limit
    p = _player(db, player_id)
    rows = h2h_repo.opponents(db, p["player_key"], scope, role, limit)
    out = [{"player_id": r["player_id"], "name": r["name"],
            "slug": player_slug(r["name"], r["player_id"]),
            "balls": r["balls"], "runs": r["runs"], "outs": r["outs"],
            "roles": sorted((r["roles"] or "").split(","))} for r in rows]
    names = players_service.display(db, [r["player_id"] for r in out])
    for r in out:
        r["full_name"] = names.get(r["player_id"], {}).get("full_name", r["name"])
    return out, {"balls": DEFS["balls"], "outs": DEFS["outs"],
                 "roles": "batter = this player batted against them; bowler = bowled to them."}
