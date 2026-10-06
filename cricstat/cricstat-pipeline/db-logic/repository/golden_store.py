"""Read-only queries for the golden-figure check (F4 §3) against the serving DB.

Kept apart from serving_store.py on purpose: that file is part of rules_sha, and a change there
forces a full rebuild.
"""
import sqlite3
from typing import Dict


def player_figures(conn: sqlite3.Connection, player_id: str, scope: str) -> Dict[str, object]:
    """Career row for one player and scope from the F4 views (empty dict if none)."""
    out: Dict[str, object] = {}
    for view in ("v_player_batting", "v_player_bowling", "v_player_fielding"):
        cur = conn.execute("SELECT * FROM %s WHERE player_id = ? AND scope = ?" % view,
                           (player_id, scope))
        row = cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            prefix = {"v_player_batting": "bat_", "v_player_bowling": "bowl_",
                      "v_player_fielding": "fld_"}[view]
            out.update({prefix + c: v for c, v in zip(cols, row)})
            out["matches"] = out.get("matches", row[cols.index("matches")])
    if out:
        out["first_date"] = conn.execute(
            "SELECT c.first_date FROM player_career c JOIN players p USING (player_key)"
            " WHERE p.player_id = ? AND c.scope = ?", (player_id, scope)).fetchone()[0]
    return out


def matches_per_year(conn: sqlite3.Connection, scope: str, gender: str) -> Dict[int, int]:
    """{year: matches} for a format key or competition slug."""
    return {int(y): n for y, n in conn.execute(
        "SELECT substr(m.start_date, 1, 4), COUNT(*) FROM matches m"
        " LEFT JOIN competitions c USING (competition_key)"
        " WHERE m.gender = ? AND (m.format_key = ? OR c.competition_slug = ?) GROUP BY 1",
        (gender, scope, scope))}


def team_record(conn: sqlite3.Connection, name: str, gender: str, team_type: str, scope: str,
                date_from: str, date_to: str) -> Dict[str, object]:
    """Team results in a date window, by format key or competition slug (F4 R19 win %)."""
    cur = conn.execute(
        "SELECT COUNT(*) AS matches, SUM(r.outcome = 'won') AS won,"
        " SUM(r.outcome = 'lost') AS lost,"
        " SUM(r.outcome = 'tied') AS tied, SUM(r.outcome = 'drawn') AS drawn,"
        " SUM(r.outcome = 'no_result') AS no_result,"
        " SUM(r.outcome = 'won') * 100.0 / NULLIF(COUNT(*) - SUM(r.outcome = 'no_result'), 0)"
        "  AS win_pct"
        " FROM team_results r JOIN teams t USING (team_key)"
        " LEFT JOIN competitions c ON c.competition_key = r.competition_key"
        " WHERE t.name = ? AND t.gender = ? AND t.team_type = ?"
        " AND (r.format_key = ? OR c.competition_slug = ?) AND r.start_date BETWEEN ? AND ?",
        (name, gender, team_type, scope, scope, date_from, date_to))
    return dict(zip([d[0] for d in cur.description], cur.fetchone()))
