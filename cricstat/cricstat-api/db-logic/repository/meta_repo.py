"""Build/status, catalog, competitions and search queries."""
import os
import sqlite3
from typing import List, Optional

from db_logic.repository.db import ServingDB


def latest_build(db: ServingDB) -> Optional[dict]:
    return db.one("SELECT build_id, built_at, mode, raw_run_id, matches, deliveries, data_as_of,"
                  " status, notes FROM build_info WHERE status = 'success'"
                  " ORDER BY build_id DESC LIMIT 1")


def recent_builds(db: ServingDB, limit: int = 5) -> List[dict]:
    return db.all("SELECT build_id, built_at, mode, matches, deliveries, data_as_of, status"
                  " FROM build_info ORDER BY build_id DESC LIMIT ?", (limit,))


def ingest_runs(raw_db: str, limit: int = 5) -> List[dict]:
    """Last runs from the raw store's log. Opened briefly and read-only: the raw store is written
    in place by the ingester, so no immutable flag, and nothing is held open."""
    if not os.path.exists(raw_db):
        return []
    conn = sqlite3.connect("file:%s?mode=ro" % raw_db, uri=True, timeout=2)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT run_id, mode, status, started_at, finished_at, added, updated, unchanged,"
            " failed, removed, active_after,"
            " json_extract(notes, '$.source_last_modified') AS source_last_modified"
            " FROM ingest_runs ORDER BY run_id DESC LIMIT ?", (limit,)).fetchall()]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def counts(db: ServingDB) -> dict:
    return db.one("SELECT (SELECT COUNT(*) FROM matches) AS matches,"
                  " (SELECT COUNT(*) FROM players) AS players,"
                  " (SELECT COUNT(*) FROM teams) AS teams,"
                  " (SELECT MIN(start_date) FROM matches) AS first_match,"
                  " (SELECT MAX(end_date) FROM matches) AS last_match")


def catalog(db: ServingDB) -> List[dict]:
    return db.all("SELECT object_name, column_name, description FROM semantic_catalog"
                  " ORDER BY object_name, column_name")


def competitions(db: ServingDB, featured: Optional[bool]) -> List[dict]:
    where = "" if featured is None else " WHERE c.is_featured = %d" % (1 if featured else 0)
    return db.all(
        "SELECT c.competition_slug, c.event_name, c.gender, c.team_type, c.is_featured,"
        " COUNT(m.match_key) AS matches, MIN(m.start_date) AS first_date,"
        " MAX(m.start_date) AS last_date, GROUP_CONCAT(DISTINCT m.season) AS seasons"
        " FROM competitions c LEFT JOIN matches m USING (competition_key)%s"
        " GROUP BY c.competition_key HAVING matches > 0"
        " ORDER BY c.is_featured DESC, matches DESC" % where)


def search_players(db: ServingDB, q: str, gender: Optional[str], limit: int) -> List[dict]:
    """Candidates whose name or a variant matches; ranked exact > prefix > word > contains, then
    by career matches. Disambiguation facts (main team, years, matches) come with each."""
    return db.all(
        "WITH hits AS ("
        "  SELECT n.player_key, MIN(CASE WHEN n.name = :q COLLATE NOCASE THEN 0"
        "   WHEN n.name LIKE :prefix THEN 1 WHEN n.name LIKE :word THEN 2 ELSE 3 END) AS rank"
        "  FROM player_names n WHERE n.name LIKE :contains GROUP BY n.player_key)"
        " SELECT p.player_id, p.name, p.unique_name, h.rank, c.gender, c.matches,"
        "  c.first_date, c.last_date, b.full_name AS wd_name, b.photo_file,"
        "  (SELECT GROUP_CONCAT(v.name, '|') FROM player_names v WHERE v.player_key = p.player_key"
        "   AND v.source = 'register_variant') AS variants,"
        "  (SELECT t.name FROM player_teams pt JOIN teams t USING (team_key)"
        "   WHERE pt.player_key = p.player_key ORDER BY t.team_type = 'club', pt.matches DESC"
        "   LIMIT 1) AS main_team"
        " FROM hits h JOIN players p USING (player_key)"
        " LEFT JOIN player_bio b USING (player_key)"
        " JOIN (SELECT player_key, gender, SUM(matches) AS matches, MIN(first_date) AS first_date,"
        "   MAX(last_date) AS last_date FROM player_career"
        "   WHERE scope IN (SELECT DISTINCT format_key FROM format_map)"
        "   GROUP BY player_key, gender) c USING (player_key)"
        " WHERE (:gender IS NULL OR c.gender = :gender)"
        " ORDER BY h.rank, c.matches DESC LIMIT :limit",
        {"q": q, "prefix": q + "%", "word": "% " + q + "%", "contains": "%" + q + "%",
         "gender": gender, "limit": limit})


def search_competitions(db: ServingDB, q: str, limit: int) -> List[dict]:
    """Only competitions that have matches (featured ones are pre-seeded by the rules)."""
    return db.all("SELECT c.competition_slug, c.event_name, c.gender, c.is_featured"
                  " FROM competitions c WHERE (c.event_name LIKE ? OR c.competition_slug LIKE ?)"
                  " AND EXISTS (SELECT 1 FROM matches m"
                  "  WHERE m.competition_key = c.competition_key)"
                  " ORDER BY c.is_featured DESC, c.event_name LIMIT ?",
                  ("%" + q + "%", "%" + q + "%", limit))
