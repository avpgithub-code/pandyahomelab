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


def display_names(db: ServingDB, player_ids: List[str]) -> List[dict]:
    """For lists of players (leaders, top performers): scorecard name, Wikidata name, photo file
    and Register full-name variants, in one query."""
    if not player_ids:
        return []
    return db.all(
        "SELECT p.player_id, p.name, b.full_name AS wd_name, b.photo_file,"
        " (SELECT GROUP_CONCAT(v.name, '|') FROM player_names v WHERE v.player_key = p.player_key"
        "  AND v.source = 'register_variant') AS variants"
        " FROM players p LEFT JOIN player_bio b USING (player_key)"
        " WHERE p.player_id IN (%s)" % ", ".join("?" * len(player_ids)), list(player_ids))
