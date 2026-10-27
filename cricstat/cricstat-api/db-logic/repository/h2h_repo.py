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


def dismissal_list(db: ServingDB, scope: str, batter_key: int, bowler_key: int) -> List[dict]:
    """Each time the bowler dismissed the batter (the same rule as matchup_outs), oldest first,
    with the match, the ball, the fielders and the batter's score in that innings."""
    return db.all(
        "SELECT m.match_id, m.start_date, v.name AS venue, v.city, x.innings_no, d.ball_label,"
        " x.kind, bi.runs, bi.balls_faced, bi.team_key, m.result, m.winner_key,"
        " (SELECT GROUP_CONCAT(f.fielder_name"
        "  || CASE f.is_substitute WHEN 1 THEN ' (sub)' ELSE '' END, ' / ')"
        "  FROM dismissal_fielders f WHERE f.match_key = x.match_key"
        "  AND f.innings_no = x.innings_no AND f.over_no = x.over_no AND f.seq = x.seq"
        "  AND f.wicket_seq = x.wicket_seq) AS fielders,"
        " t.name AS team, o.name AS opponent"
        " FROM dismissals x JOIN matches m ON m.match_key = x.match_key"
        " JOIN venues v ON v.venue_key = m.venue_key"
        " JOIN innings i ON i.match_key = x.match_key AND i.innings_no = x.innings_no"
        " LEFT JOIN deliveries d ON d.match_key = x.match_key AND d.innings_no = x.innings_no"
        "  AND d.over_no = x.over_no AND d.seq = x.seq"
        " LEFT JOIN batting_innings bi ON bi.match_key = x.match_key"
        "  AND bi.innings_no = x.innings_no AND bi.player_key = x.player_out_key"
        " LEFT JOIN teams t ON t.team_key = bi.team_key"
        " LEFT JOIN teams o ON o.team_key = bi.opponent_key"
        " WHERE x.player_out_key = ? AND x.bowler_key = ? AND m.format_key = ?"
        " AND x.credited_to_bowler = 1 AND x.counts_as_out = 1 AND i.is_super_over = 0"
        " ORDER BY m.start_date, x.innings_no, x.over_no, x.seq",
        (batter_key, bowler_key, scope))
