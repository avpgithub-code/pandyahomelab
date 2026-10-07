"""Queries behind the server-rendered page heads and the sitemap (P0.6)."""
from typing import List

from db_logic.repository.db import ServingDB

INTL = ("TEST", "ODI", "T20I")


def name_variants(db: ServingDB, player_key: int) -> List[str]:
    """Names the Cricsheet Register lists for one person (e.g. 'Virat Kohli' for 'V Kohli')."""
    return [r["name"] for r in db.all("SELECT name FROM player_names WHERE player_key = ?"
                                      " AND source = 'register_variant' ORDER BY name",
                                      (player_key,))]


def indexable_players(db: ServingDB, min_intl: int, min_league: int) -> List[dict]:
    """Players with enough cricket for a page worth indexing: min_intl official internationals
    (Test + ODI + T20I) or min_league featured-league matches. Same rule as pages_service."""
    return db.all(
        "SELECT p.player_id, p.name, MAX(c.last_date) AS last_date FROM player_career c"
        " JOIN players p USING (player_key) WHERE c.scope IN ('TEST', 'ODI', 'T20I', 'LEAGUES')"
        " GROUP BY c.player_key"
        " HAVING SUM(CASE WHEN c.scope = 'LEAGUES' THEN 0 ELSE c.matches END) >= ?"
        " OR SUM(CASE WHEN c.scope = 'LEAGUES' THEN c.matches ELSE 0 END) >= ?"
        " ORDER BY p.player_id", (min_intl, min_league))
