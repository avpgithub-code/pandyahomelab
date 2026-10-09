"""Team queries. team_results holds one row per team per match with play (F3 §6)."""
from typing import List, Optional

from db_logic.repository.db import ServingDB
from db_logic.repository.players_repo import _dates


def all_teams(db: ServingDB) -> List[dict]:
    """Every team with its match count (played matches), for slugs, lists and search."""
    return db.all("SELECT t.team_key, t.name, t.gender, t.team_type, COUNT(r.match_key) AS matches,"
                  " MIN(r.start_date) AS first_date, MAX(r.start_date) AS last_date"
                  " FROM teams t LEFT JOIN team_results r USING (team_key)"
                  " GROUP BY t.team_key ORDER BY matches DESC")


def record(db: ServingDB, team_key: int, scope: Optional[str], date_from: Optional[str] = None,
           date_to: Optional[str] = None) -> List[dict]:
    if scope or date_from or date_to:
        where, args = db.scopes().clause(scope, "r") if scope else ("1", [])
        dates, dargs = _dates("r.start_date", date_from, date_to)
        return db.all(
            "SELECT COUNT(*) AS matches, SUM(r.outcome = 'won') AS won,"
            " SUM(r.outcome = 'lost') AS lost, SUM(r.outcome = 'tied') AS tied,"
            " SUM(r.outcome = 'drawn') AS drawn, SUM(r.outcome = 'no_result') AS no_result"
            " FROM team_results r WHERE r.team_key = ? AND %s %s" % (where, dates),
            [team_key] + args + dargs)
    return db.all("SELECT format_key, matches, won, lost, tied, drawn, no_result, win_pct"
                  " FROM v_team_record WHERE team_key = ?"
                  " ORDER BY CASE format_key WHEN 'TEST' THEN 1 WHEN 'ODI' THEN 2"
                  " WHEN 'T20I' THEN 3 ELSE 4 END, matches DESC", (team_key,))


def records(db: ServingDB, scope: str, date_from: Optional[str] = None,
            date_to: Optional[str] = None) -> List[dict]:
    """Every team's record in one scope (and date window), one row per team: the map's bulk read."""
    where, args = db.scopes().clause(scope, "r")
    dates, dargs = _dates("r.start_date", date_from, date_to)
    return db.all(
        "SELECT r.team_key, COUNT(*) AS matches, SUM(r.outcome = 'won') AS won,"
        " SUM(r.outcome = 'lost') AS lost, SUM(r.outcome = 'tied') AS tied,"
        " SUM(r.outcome = 'drawn') AS drawn, SUM(r.outcome = 'no_result') AS no_result,"
        " MAX(r.start_date) AS last_date"
        " FROM team_results r WHERE %s %s GROUP BY r.team_key" % (where, dates), args + dargs)


def results(db: ServingDB, team_key: int, scope: Optional[str], date_from: Optional[str],
            date_to: Optional[str], limit: int, offset: int) -> List[dict]:
    where, args = db.scopes().clause(scope, "r") if scope else ("1", [])
    dates, dargs = _dates("r.start_date", date_from, date_to)
    return db.all(
        "SELECT m.match_id, r.start_date, r.format_key, o.name AS opponent, o.gender,"
        " o.team_type, r.outcome, r.margin_runs, r.margin_wickets, m.win_by_innings, m.method,"
        " m.decided_by, w.name AS winner, v.name AS venue, v.city, r.home_away,"
        " c.event_name AS competition"
        " FROM team_results r JOIN matches m USING (match_key)"
        " JOIN teams o ON o.team_key = r.opponent_key JOIN venues v ON v.venue_key = r.venue_key"
        " LEFT JOIN teams w ON w.team_key = m.winner_key"
        " LEFT JOIN competitions c ON c.competition_key = r.competition_key"
        " WHERE r.team_key = ? AND %s %s ORDER BY r.start_date DESC, m.match_id DESC"
        " LIMIT ? OFFSET ?" % (where, dates), [team_key] + args + dargs + [limit, offset])


def head_to_head(db: ServingDB, team_key: int, scope: Optional[str],
                 opponent_key: Optional[int]) -> List[dict]:
    where, args = db.scopes().clause(scope, "r") if scope else ("1", [])
    opp = " AND r.opponent_key = ?" if opponent_key else ""
    oargs = [opponent_key] if opponent_key else []
    return db.all(
        "SELECT o.name AS opponent, o.gender, o.team_type, r.opponent_key, r.format_key,"
        " COUNT(*) AS matches, SUM(r.outcome = 'won') AS won, SUM(r.outcome = 'lost') AS lost,"
        " SUM(r.outcome = 'tied') AS tied, SUM(r.outcome = 'drawn') AS drawn,"
        " SUM(r.outcome = 'no_result') AS no_result, MAX(r.start_date) AS last_played,"
        " (SELECT r2.outcome FROM team_results r2 WHERE r2.team_key = r.team_key"
        "  AND r2.opponent_key = r.opponent_key AND r2.format_key = r.format_key"
        "  ORDER BY r2.start_date DESC LIMIT 1) AS last_outcome"
        " FROM team_results r JOIN teams o ON o.team_key = r.opponent_key"
        " WHERE r.team_key = ? AND %s%s"
        " GROUP BY r.opponent_key, r.format_key ORDER BY matches DESC" % (where, opp),
        [team_key] + args + oargs)


def home_away(db: ServingDB, team_key: int, scope: Optional[str]) -> List[dict]:
    where, args = db.scopes().clause(scope, "r") if scope else ("1", [])
    return db.all(
        "SELECT COALESCE(r.home_away, 'unknown') AS where_played, COUNT(*) AS matches,"
        " SUM(r.outcome = 'won') AS won, SUM(r.outcome = 'lost') AS lost,"
        " SUM(r.outcome = 'tied') AS tied, SUM(r.outcome = 'drawn') AS drawn,"
        " SUM(r.outcome = 'no_result') AS no_result"
        " FROM team_results r WHERE r.team_key = ? AND %s GROUP BY 1"
        " ORDER BY CASE where_played WHEN 'home' THEN 1 WHEN 'away' THEN 2"
        " WHEN 'neutral' THEN 3 ELSE 4 END" % where, [team_key] + args)


def years(db: ServingDB, team_key: int, scope: Optional[str]) -> List[dict]:
    where, args = db.scopes().clause(scope, "r") if scope else ("1", [])
    return db.all(
        "SELECT CAST(substr(r.start_date, 1, 4) AS INTEGER) AS year, COUNT(*) AS matches,"
        " SUM(r.outcome = 'won') AS won, SUM(r.outcome = 'lost') AS lost,"
        " SUM(r.outcome = 'tied') AS tied, SUM(r.outcome = 'drawn') AS drawn,"
        " SUM(r.outcome = 'no_result') AS no_result"
        " FROM team_results r WHERE r.team_key = ? AND %s GROUP BY 1 ORDER BY 1"
        % where, [team_key] + args)


def top_players(db: ServingDB, team_key: int, scope: Optional[str], metric: str,
                date_from: Optional[str], date_to: Optional[str], limit: int) -> List[dict]:
    """Leaders for this team only: counts what players did while playing for it.
    The team's matches come from team_results (indexed by team); atoms are then read by their
    primary key, which starts with match_key, instead of scanning every innings."""
    where, args = db.scopes().clause(scope, "r") if scope else ("1", [])
    dates, dargs = _dates("r.start_date", date_from, date_to)
    matches = ("a.match_key IN (SELECT r.match_key FROM team_results r WHERE r.team_key = ?"
               " AND %s %s)" % (where, dates))
    if metric == "runs":
        sql = ("SELECT p.player_id, p.name, COUNT(*) AS innings, SUM(a.runs) AS runs,"
               " SUM(a.balls_faced) AS balls_faced, SUM(a.is_out) AS outs,"
               " COUNT(DISTINCT a.match_key) AS matches FROM batting_innings a"
               " JOIN players p USING (player_key)"
               " WHERE %s AND a.team_key = ? AND a.is_super_over = 0"
               " GROUP BY a.player_key ORDER BY runs DESC, innings ASC LIMIT ?")
    else:
        sql = ("SELECT p.player_id, p.name, COUNT(*) AS innings, SUM(a.wickets) AS wickets,"
               " SUM(a.legal_balls) AS legal_balls, SUM(a.runs_conceded) AS runs_conceded,"
               " COUNT(DISTINCT a.match_key) AS matches FROM bowling_innings a"
               " JOIN players p USING (player_key)"
               " WHERE %s AND a.team_key = ? AND a.is_super_over = 0"
               " GROUP BY a.player_key ORDER BY wickets DESC, runs_conceded ASC LIMIT ?")
    return db.all(sql % matches, [team_key] + args + dargs + [team_key, limit])
