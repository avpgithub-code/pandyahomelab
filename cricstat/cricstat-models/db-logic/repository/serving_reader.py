"""Read-only access to the serving DB (cricstat.sqlite), by stable identifiers only.

The serving surrogates (team_key, match_key, player_key) are rowids in load order and can be
renumbered by a full build, so nothing here returns them to callers: matches are identified by
match_id (the ESPNcricinfo id), teams by (name, gender, team_type), players by the Cricsheet
player_id.
"""
import csv
import sqlite3
from typing import Dict, List, Set

# Composite and invitational sides are not national teams; they never enter the ratings.
COMPOSITE_SIDES = frozenset({"Asia XI", "Africa XI", "ICC World XI", "World XI"})


def connect(path: str) -> sqlite3.Connection:
    """Open the serving DB read-only (immutable: the pipeline only ever swaps in a new file)."""
    conn = sqlite3.connect("file:%s?mode=ro&immutable=1" % path, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def build_info(conn: sqlite3.Connection) -> Dict[str, str]:
    row = conn.execute("SELECT * FROM build_info ORDER BY build_id DESC LIMIT 1").fetchone()
    return dict(row) if row else {}


def all_match_ids(conn: sqlite3.Connection) -> Set[str]:
    """Every match_id in the serving DB (all formats); a supplement row must not collide."""
    return {r[0] for r in conn.execute("SELECT match_id FROM matches")}


def men_international_teams(conn: sqlite3.Connection) -> Set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM teams WHERE gender = 'male' AND team_type = 'international'")}


def men_odi_results(conn: sqlite3.Connection) -> List[Dict[str, object]]:
    """Official men's ODIs, oldest first, one row per match, keyed by match_id.
    team1/team2 follow the scorecard order; home_away is team1's view (the build's F4 §2 rule)."""
    sql = """
        SELECT m.match_id, m.start_date, a.name AS team1, b.name AS team2,
               v.country AS venue_country,
               tr.home_away AS team1_home_away, m.result, w.name AS winner, m.method, m.decided_by,
               m.has_deliveries, c.event_name AS event, m.event_stage
          FROM matches m
          JOIN teams a ON a.team_key = m.team1_key
          JOIN teams b ON b.team_key = m.team2_key
          JOIN venues v ON v.venue_key = m.venue_key
          LEFT JOIN teams w ON w.team_key = m.winner_key
          LEFT JOIN team_results tr ON tr.match_key = m.match_key AND tr.team_key = m.team1_key
          LEFT JOIN competitions c ON c.competition_key = m.competition_key
         WHERE m.gender = 'male' AND m.match_type = 'ODI' AND m.team_type = 'international'
         ORDER BY m.start_date, m.match_id"""
    out = []
    for r in conn.execute(sql):
        if r["team1"] in COMPOSITE_SIDES or r["team2"] in COMPOSITE_SIDES:
            continue
        d = dict(r)
        d["source"] = "cricsheet"
        d["has_play"] = 1           # Cricsheet only publishes matches where a ball was bowled
        out.append(d)
    return out


def city_countries(venue_map_path: str) -> Dict[str, str]:
    """City → country from the reviewed sql/venue_map.csv, only where the city is unambiguous."""
    seen: Dict[str, Set[str]] = {}
    with open(venue_map_path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            city = (r.get("canonical_city") or r.get("city") or "").strip()
            if city and r.get("country"):
                seen.setdefault(city, set()).add(r["country"].strip())
    return {c: next(iter(s)) for c, s in seen.items() if len(s) == 1}
