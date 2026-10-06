"""Player queries. Counts come from the marts and atoms; ratios from the F4 views where a view
covers the request (career), otherwise application-logic/services/metrics.py computes them."""
from typing import List, Optional

from db_logic.repository.db import ServingDB


def identity(db: ServingDB, player_id: str) -> Optional[dict]:
    return db.one("SELECT p.player_key, p.player_id, p.name, p.unique_name, b.wikidata_qid,"
                  " b.date_of_birth, b.birthplace, b.country_for_sport"
                  " FROM players p LEFT JOIN player_bio b USING (player_key)"
                  " WHERE p.player_id = ?", (player_id,))


def teams(db: ServingDB, player_key: int) -> List[dict]:
    return db.all("SELECT t.name, t.gender, t.team_type, pt.matches, pt.first_date, pt.last_date"
                  " FROM player_teams pt JOIN teams t USING (team_key)"
                  " WHERE pt.player_key = ? ORDER BY t.team_type = 'club', pt.matches DESC",
                  (player_key,))


def scopes_played(db: ServingDB, player_key: int) -> List[dict]:
    return db.all("SELECT scope, gender, matches, first_date, last_date FROM player_career"
                  " WHERE player_key = ? ORDER BY matches DESC", (player_key,))


def career(db: ServingDB, player_key: int, scope: str) -> dict:
    out = {}
    for view, key in (("v_player_batting", "batting"), ("v_player_bowling", "bowling"),
                      ("v_player_fielding", "fielding")):
        out[key] = db.one("SELECT * FROM %s WHERE player_key = ? AND scope = ?" % view,
                          (player_key, scope))
    out["matches"] = db.one("SELECT matches, gender, first_date, last_date FROM player_career"
                            " WHERE player_key = ? AND scope = ?", (player_key, scope))
    return out


def years(db: ServingDB, player_key: int, scope: str) -> List[dict]:
    return db.all("SELECT year, matches, runs, bat_innings, not_outs, balls_faced, wickets,"
                  " legal_balls, runs_conceded FROM player_year"
                  " WHERE player_key = ? AND scope = ? ORDER BY year", (player_key, scope))


def phases(db: ServingDB, player_key: int, scope: str) -> List[dict]:
    where, args = db.scopes().clause(scope, "s")
    return db.all(
        "SELECT f.format_family, s.phase, d.label, d.from_over,"
        " SUM(s.bat_runs) AS bat_runs, SUM(s.bat_balls) AS bat_balls, SUM(s.bat_outs) AS bat_outs,"
        " SUM(s.bowl_balls) AS bowl_balls, SUM(s.bowl_runs) AS bowl_runs,"
        " SUM(s.bowl_wkts) AS bowl_wkts"
        " FROM phase_stats s"
        " JOIN (SELECT DISTINCT format_key, format_family FROM format_map) f USING (format_key)"
        " JOIN phase_defs d ON d.format_family = f.format_family AND d.phase = s.phase"
        " WHERE s.player_key = ? AND %s"
        " GROUP BY f.format_family, s.phase, d.label, d.from_over"
        " ORDER BY f.format_family, d.from_over" % where, [player_key] + args)


_SPLIT = {
    "opponent": ("o.name AS label, o.gender, o.team_type", "teams o ON o.team_key = a.opponent_key",
                 "a.opponent_key"),
    "venue": ("cv.name AS label, cv.city, cv.country", "venues v ON v.venue_key = a.venue_key"
              " JOIN venues cv ON cv.venue_key = COALESCE(v.canonical_venue_key, v.venue_key)",
              "cv.venue_key"),
    "season": ("a.season AS label", None, "a.season"),
}


def splits(db: ServingDB, player_key: int, scope: str, by: str) -> dict:
    """Batting and bowling totals grouped by opponent, canonical venue or season."""
    cols, join, group = _SPLIT[by]
    out = {}
    for kind, table, sums in (
            ("batting", "batting_innings", "COUNT(*) AS innings, SUM(a.runs) AS runs,"
             " SUM(a.balls_faced) AS balls_faced, SUM(a.is_out) AS outs,"
             " SUM(a.runs >= 100) AS hundreds, SUM(a.runs BETWEEN 50 AND 99) AS fifties"),
            ("bowling", "bowling_innings", "COUNT(*) AS innings, SUM(a.legal_balls) AS legal_balls,"
             " SUM(a.runs_conceded) AS runs_conceded, SUM(a.wickets) AS wickets")):
        where, args = db.scopes().clause(scope, "a")
        out[kind] = db.all(
            "SELECT %s, %s, COUNT(DISTINCT a.match_key) AS matches FROM %s a %s"
            " WHERE a.player_key = ? AND a.is_super_over = 0 AND %s GROUP BY %s"
            % (cols, sums, table, ("JOIN " + join) if join else "", where, group),
            [player_key] + args)
    return out


def innings(db: ServingDB, player_key: int, scope: str, date_from: Optional[str],
            date_to: Optional[str], limit: int, offset: int) -> List[dict]:
    """One row per match: the player's batting and bowling in it (super overs excluded)."""
    where, args = db.scopes().clause(scope, "m")
    dates, dargs = _dates("m.start_date", date_from, date_to)
    return db.all(
        "SELECT m.match_id, m.start_date, m.format_key, m.gender, t.name AS team,"
        " o.name AS opponent, o.team_type, v.name AS venue, v.city, mp.team_key, m.result,"
        " w.name AS winner"
        " FROM match_players mp JOIN matches m USING (match_key)"
        " JOIN teams t ON t.team_key = mp.team_key"
        " JOIN teams o ON o.team_key = CASE WHEN m.team1_key = mp.team_key THEN m.team2_key"
        "  ELSE m.team1_key END"
        " JOIN venues v ON v.venue_key = m.venue_key"
        " LEFT JOIN teams w ON w.team_key = m.winner_key"
        " WHERE mp.player_key = ? AND m.has_deliveries = 1 AND %s %s"
        " ORDER BY m.start_date DESC, m.match_id DESC LIMIT ? OFFSET ?" % (where, dates),
        [player_key] + args + dargs + [limit, offset])


def innings_detail(db: ServingDB, player_key: int, match_ids: List[str]) -> dict:
    if not match_ids:
        return {"batting": [], "bowling": []}
    marks = ", ".join("?" * len(match_ids))
    bat = db.all("SELECT m.match_id, a.innings_no, a.batting_position, a.runs, a.balls_faced,"
                 " a.fours, a.sixes, a.is_out, a.dismissal_kind FROM batting_innings a"
                 " JOIN matches m USING (match_key) WHERE a.player_key = ? AND a.is_super_over = 0"
                 " AND m.match_id IN (%s) ORDER BY a.innings_no" % marks, [player_key] + match_ids)
    bowl = db.all("SELECT m.match_id, a.innings_no, a.legal_balls, a.runs_conceded, a.wickets,"
                  " a.maidens, a.wides, a.noballs, a.dots FROM bowling_innings a"
                  " JOIN matches m USING (match_key) WHERE a.player_key = ?"
                  " AND a.is_super_over = 0 AND m.match_id IN (%s) ORDER BY a.innings_no"
                  % marks, [player_key] + match_ids)
    return {"batting": bat, "bowling": bowl}


def _dates(col: str, date_from: Optional[str], date_to: Optional[str]):
    sql, args = "", []
    if date_from:
        sql += " AND %s >= ?" % col
        args.append(date_from)
    if date_to:
        sql += " AND %s <= ?" % col
        args.append(date_to)
    return sql, args
