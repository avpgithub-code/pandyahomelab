"""Match list with innings scores, and leaderboards (F5 §3 "Matches" / "Leaderboards")."""
from typing import Dict, List, Optional

from db_logic.repository.db import ServingDB
from db_logic.repository.players_repo import _dates


def _match_filter(db: ServingDB, scope: Optional[str], gender: Optional[str],
                  team_key: Optional[int], date_from: Optional[str], date_to: Optional[str]):
    where, args = db.scopes().clause(scope, "m") if scope else ("1", [])
    sql, params = " AND %s" % where, list(args)
    if gender:
        sql += " AND m.gender = ?"
        params.append(gender)
    if team_key:
        sql += " AND (m.team1_key = ? OR m.team2_key = ?)"
        params += [team_key, team_key]
    dates, dargs = _dates("m.start_date", date_from, date_to)
    return sql + dates, params + dargs


def matches(db: ServingDB, scope: Optional[str], gender: Optional[str], team_key: Optional[int],
            date_from: Optional[str], date_to: Optional[str], limit: int,
            offset: int) -> List[dict]:
    """Matches with play, newest first."""
    where, args = _match_filter(db, scope, gender, team_key, date_from, date_to)
    return db.all(
        "SELECT m.match_id, m.start_date, m.end_date, m.format_key, m.gender, m.result,"
        " m.win_by_runs, m.win_by_wickets, m.win_by_innings, m.method, m.decided_by,"
        " m.team1_key, m.team2_key, w.name AS winner, v.name AS venue, v.city,"
        " c.event_name AS competition, c.competition_slug, c.is_featured"
        " FROM matches m JOIN venues v ON v.venue_key = m.venue_key"
        " LEFT JOIN teams w ON w.team_key = m.winner_key"
        " LEFT JOIN competitions c ON c.competition_key = m.competition_key"
        " WHERE m.has_deliveries = 1 %s ORDER BY m.end_date DESC, m.match_id DESC"
        " LIMIT ? OFFSET ?" % where, args + [limit, offset])


def innings_scores(db: ServingDB, match_ids: List[str]) -> Dict[str, List[dict]]:
    """{match_id: [{innings_no, team_key, runs, wickets, legal_balls, declared, super_over}]}"""
    if not match_ids:
        return {}
    marks = ", ".join("?" * len(match_ids))
    out: Dict[str, List[dict]] = {}
    for r in db.all("SELECT m.match_id, i.innings_no, i.batting_team_key AS team_key,"
                    " i.total_runs AS runs, i.total_wickets AS wickets, i.legal_balls,"
                    " i.declared, i.forfeited, i.is_super_over, m.balls_per_over"
                    " FROM innings i JOIN matches m USING (match_key)"
                    " WHERE m.match_id IN (%s) ORDER BY m.match_id, i.innings_no" % marks,
                    match_ids):
        out.setdefault(r.pop("match_id"), []).append(r)
    return out


def leaders(db: ServingDB, kind: str, scope: Optional[str], gender: Optional[str],
            date_from: Optional[str], date_to: Optional[str], limit: int) -> List[dict]:
    """Top run-scorers (kind='batting') or wicket-takers ('bowling'), super overs excluded.
    Matches are chosen first (indexed), then atoms are read by primary key."""
    where, args = _match_filter(db, scope, gender, None, date_from, date_to)
    chosen = "a.match_key IN (SELECT m.match_key FROM matches m WHERE m.has_deliveries = 1 %s)" \
        % where
    if kind == "batting":
        sql = ("SELECT p.player_id, p.name, COUNT(*) AS innings, COUNT(DISTINCT a.match_key) AS"
               " matches, SUM(a.runs) AS runs, SUM(a.balls_faced) AS balls_faced,"
               " SUM(a.is_out) AS outs, MAX(a.runs) AS best,"
               " (SELECT t.name FROM batting_innings b JOIN teams t ON t.team_key = b.team_key"
               "  WHERE b.player_key = a.player_key ORDER BY b.start_date DESC LIMIT 1) AS team"
               " FROM batting_innings a JOIN players p USING (player_key)"
               " WHERE %s AND a.is_super_over = 0 GROUP BY a.player_key"
               " ORDER BY runs DESC, innings ASC LIMIT ?")
    else:
        sql = ("SELECT p.player_id, p.name, COUNT(*) AS innings, COUNT(DISTINCT a.match_key) AS"
               " matches, SUM(a.wickets) AS wickets, SUM(a.legal_balls) AS legal_balls,"
               " SUM(a.runs_conceded) AS runs_conceded,"
               " (SELECT t.name FROM bowling_innings b JOIN teams t ON t.team_key = b.team_key"
               "  WHERE b.player_key = a.player_key ORDER BY b.start_date DESC LIMIT 1) AS team"
               " FROM bowling_innings a JOIN players p USING (player_key)"
               " WHERE %s AND a.is_super_over = 0 GROUP BY a.player_key"
               " ORDER BY wickets DESC, runs_conceded ASC LIMIT ?")
    return db.all(sql % chosen, args + [limit])
