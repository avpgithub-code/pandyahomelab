"""Head to Head queries (docs/h2h-plan.md): batter v bowler counts from the `matchups` and
`matchup_outs` marts the pipeline builds. Counts only; ratios are computed by the service."""
from typing import List, Optional

from db_logic.repository.db import ServingDB

_COLS = "balls, runs, dots, fours, sixes, outs, matches, first_date, last_date"


def available(db: ServingDB) -> bool:
    """False until the pipeline has built the matchup marts (a DB from before H1)."""
    return db.cached("h2h_available", lambda: db.one(
        "SELECT 1 AS ok FROM sqlite_master WHERE type = 'table' AND name = 'matchups'") is not None)


def matchup(db: ServingDB, scope: str, batter_key: int, bowler_key: int) -> Optional[dict]:
    return db.one("SELECT %s FROM matchups WHERE scope = ? AND batter_key = ? AND bowler_key = ?"
                  % _COLS, (scope, batter_key, bowler_key))


def outs(db: ServingDB, scope: str, batter_key: int, bowler_key: int) -> List[dict]:
    return db.all("SELECT kind, n FROM matchup_outs WHERE scope = ? AND batter_key = ?"
                  " AND bowler_key = ? ORDER BY n DESC, kind", (scope, batter_key, bowler_key))


def balls_by_scope(db: ServingDB, a_key: int, b_key: int) -> List[dict]:
    """Balls between the two in each format, both directions (for the format tabs)."""
    return db.all("SELECT scope, SUM(balls) AS balls FROM matchups"
                  " WHERE scope IN ('ODI', 'TEST', 'T20I')"          # primary-key lookups
                  " AND ((batter_key = ? AND bowler_key = ?)"
                  " OR (batter_key = ? AND bowler_key = ?))"
                  " GROUP BY scope", (a_key, b_key, b_key, a_key))


def opponents(db: ServingDB, player_key: int, scope: str, role: str, limit: int) -> List[dict]:
    """The players this one met most (by balls), as batter, as bowler or either way."""
    parts, args = [], []
    if role in ("batter", "any"):
        parts.append("SELECT bowler_key AS other, balls, runs, outs, 'batter' AS role"
                     " FROM matchups WHERE scope = ? AND batter_key = ?")
        args += [scope, player_key]
    if role in ("bowler", "any"):
        parts.append("SELECT batter_key AS other, balls, runs, outs, 'bowler' AS role"
                     " FROM matchups WHERE scope = ? AND bowler_key = ?")
        args += [scope, player_key]
    return db.all(
        "SELECT p.player_id, p.name, SUM(u.balls) AS balls, SUM(u.runs) AS runs,"
        " SUM(u.outs) AS outs, GROUP_CONCAT(DISTINCT u.role) AS roles"
        " FROM (%s) u JOIN players p ON p.player_key = u.other"
        " GROUP BY p.player_key ORDER BY balls DESC, p.name LIMIT ?" % " UNION ALL ".join(parts),
        args + [limit])
