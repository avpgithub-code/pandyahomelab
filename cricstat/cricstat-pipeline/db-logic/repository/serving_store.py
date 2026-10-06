"""Serving DB (data/db/cricstat.sqlite): schema, surrogate keys, per-match writes, marts.

The schema is exactly cricstat/sql/serving_schema.sql, the rules are reference_data.sql, the ratio
views are semantic_views.sql and the agent descriptions are semantic_catalog.sql. This module
never restates a rule; it loads those files. A full build creates the CREATE INDEX statements
after the bulk load (same final schema, much faster load).
"""
import os
import re
import sqlite3
from typing import Dict, Iterable, List, Optional, Tuple

from db_logic.transforms.match_facts import MatchFacts, Rules

MARTS_SQL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "marts", "marts.sql")
_INDEX_RE = re.compile(r"^CREATE INDEX [^;]+;\s*$", re.MULTILINE)
_VIEW_RE = re.compile(r"^CREATE VIEW (\w+)", re.MULTILINE)

# Per-match tables, children first (delete order for an incremental rebuild).
MATCH_TABLES = ("phase_stats", "fielding_events", "bowling_innings", "batting_innings",
                "team_results", "replacements", "reviews", "dismissal_fielders", "dismissals",
                "deliveries", "miscounted_overs", "powerplays", "innings_absent_hurt", "innings",
                "match_officials", "player_of_match", "match_players", "matches")


def read_sql(sql_dir: str, name: str) -> str:
    with open(os.path.join(sql_dir, name), encoding="utf-8") as f:
        return f.read()


def create_schema(conn: sqlite3.Connection, sql_dir: str, defer_indexes: bool = False) -> List[str]:
    """Tables + reference rows + views. Returns the CREATE INDEX statements still to run."""
    schema = read_sql(sql_dir, "serving_schema.sql")
    deferred = []
    if defer_indexes:
        deferred = [m.group(0).strip() for m in _INDEX_RE.finditer(schema)]
        schema = _INDEX_RE.sub("", schema)
    conn.executescript(schema)
    conn.executescript(read_sql(sql_dir, "reference_data.sql"))
    create_views(conn, sql_dir)
    return deferred


def create_views(conn: sqlite3.Connection, sql_dir: str) -> None:
    """(Re)create the F4 views: drops every existing view first, so an edit to
    semantic_views.sql takes effect on the next incremental build."""
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'view'").fetchall():
        conn.execute("DROP VIEW %s" % name)
    conn.executescript(read_sql(sql_dir, "semantic_views.sql"))


def load_catalog(conn: sqlite3.Connection, sql_dir: str) -> int:
    conn.execute("DELETE FROM semantic_catalog")
    conn.executescript(read_sql(sql_dir, "semantic_catalog.sql"))
    return conn.execute("SELECT COUNT(*) FROM semantic_catalog").fetchone()[0]


def load_rules(conn: sqlite3.Connection) -> Rules:
    formats = {(mt, tt, bpo): (fk, fam, lvl) for mt, tt, bpo, fk, fam, lvl in conn.execute(
        "SELECT match_type, team_type, balls_per_over, format_key, format_family, level"
        " FROM format_map")}
    kinds = {k: (c, o) for k, c, o in conn.execute(
        "SELECT kind, credited_to_bowler, counts_as_out FROM dismissal_kinds")}
    phases: Dict[str, list] = {}
    for fam, phase, lo, hi in conn.execute(
            "SELECT format_family, phase, from_over, to_over FROM phase_defs ORDER BY from_over"):
        phases.setdefault(fam, []).append((phase, lo, hi))
    return Rules(formats, kinds, phases)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class Keys:
    """Get-or-create surrogate keys for the dimension tables, cached in memory."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.teams = {(n, g, t): k for k, n, g, t in conn.execute(
            "SELECT team_key, name, gender, team_type FROM teams")}
        self.venues = {(n, c): k for k, n, c in conn.execute(
            "SELECT venue_key, name, city FROM venues")}
        self.competitions = {(n, g, t): k for k, n, g, t in conn.execute(
            "SELECT competition_key, event_name, gender, team_type FROM competitions")}
        self.players = {p: k for k, p in conn.execute("SELECT player_key, player_id FROM players")}

    def team(self, name: str, gender: str, team_type: str) -> int:
        key = (name, gender, team_type)
        if key not in self.teams:
            self.teams[key] = self.conn.execute(
                "INSERT INTO teams (name, gender, team_type) VALUES (?,?,?)", key).lastrowid
        return self.teams[key]

    def venue(self, name: str, city: Optional[str]) -> int:
        key = (name, city)
        if key not in self.venues:
            self.venues[key] = self.conn.execute(
                "INSERT INTO venues (name, city) VALUES (?,?)", key).lastrowid
        return self.venues[key]

    def competition(self, name: Optional[str], gender: str, team_type: str) -> Optional[int]:
        if not name:
            return None
        key = (name, gender, team_type)
        if key not in self.competitions:   # featured ones are pre-seeded by reference_data.sql
            self.competitions[key] = self.conn.execute(
                "INSERT INTO competitions (event_name, gender, team_type, competition_slug,"
                " is_featured) VALUES (?,?,?,?,0)", key + (slugify(name),)).lastrowid
        return self.competitions[key]

    def player(self, player_id: str, name: str) -> int:
        """Players normally come from the Register first; an id seen only in a match registry
        (newer than our people.csv) is added with its scorecard name until the next register."""
        if player_id not in self.players:
            self.players[player_id] = self.conn.execute(
                "INSERT INTO players (player_id, name, unique_name) VALUES (?,?,?)",
                (player_id, name, name)).lastrowid
        return self.players[player_id]


def _ins(conn, table: str, cols: Tuple[str, ...], rows: Iterable[tuple]) -> None:
    conn.executemany("INSERT INTO %s (%s) VALUES (%s)" % (table, ", ".join(cols),
                                                          ", ".join("?" * len(cols))), rows)


def insert_match(conn: sqlite3.Connection, keys: Keys, f: MatchFacts, sha256: str,
                 revision: Optional[int]) -> int:
    m = f.match
    g, tt = m["gender"], m["team_type"]
    names = ({m["team1"], m["team2"], m["winner"], m["toss_winner"]}
             | {r[0] for r in f.match_players} | {r[4] for r in f.replacements}
             | {r[3] for r in f.reviews} | {i["team"] for i in f.innings}
             | {i["opponent"] for i in f.innings})
    team = {name: keys.team(name, g, tt) for name in names - {None}}
    player = {p: keys.player(p, n) for p, n in f.players.items()}
    venue_key = keys.venue(m["venue"], m["city"])
    comp_key = keys.competition(m["event_name"], g, tt)
    mk = conn.execute(
        "INSERT INTO matches (match_id, match_type, team_type, gender, balls_per_over, format_key,"
        " overs_limit, match_type_number, competition_key, season, event_match_number,"
        " event_stage, event_group, start_date, end_date, n_days, venue_key, team1_key, team2_key,"
        " toss_winner_key, toss_decision, result, winner_key, win_by_runs, win_by_wickets,"
        " win_by_innings, method, decided_by, has_deliveries, source_sha256, source_revision)"
        " VALUES (%s)" % ", ".join("?" * 31),
        (f.match_id, m["match_type"], tt, g, m["balls_per_over"], m["format_key"],
         m["overs_limit"], m["match_type_number"], comp_key, m["season"], m["event_match_number"],
         m["event_stage"], m["event_group"], m["start_date"], m["end_date"], m["n_days"],
         venue_key, team[m["team1"]], team[m["team2"]], team.get(m["toss_winner"]),
         m["toss_decision"], m["result"], team.get(m["winner"]), m["win_by_runs"],
         m["win_by_wickets"], m["win_by_innings"], m["method"], m["decided_by"],
         m["has_deliveries"], sha256, revision)).lastrowid

    conn.executemany("INSERT OR IGNORE INTO match_players VALUES (?,?,?,?)",
                     ((mk, team[t], player[p], role) for t, p, role in f.match_players))
    _ins(conn, "player_of_match", ("match_key", "player_key"),
         ((mk, player[p]) for p in f.player_of_match))
    _ins(conn, "match_officials", ("match_key", "role", "name"),
         ((mk, r, n) for r, n in f.officials))
    _ins(conn, "innings", ("match_key", "innings_no", "batting_team_key", "bowling_team_key",
                           "is_super_over", "declared", "forfeited", "target_runs", "target_overs",
                           "penalty_runs_pre", "penalty_runs_post", "total_runs", "total_wickets",
                           "legal_balls"),
         ((mk, i["innings_no"], team[i["team"]], team[i["opponent"]], i["is_super_over"],
           i["declared"], i["forfeited"], i["target_runs"], i["target_overs"],
           i["penalty_runs_pre"], i["penalty_runs_post"], i["total_runs"], i["total_wickets"],
           i["legal_balls"])
          for i in f.innings))
    _ins(conn, "innings_absent_hurt", ("match_key", "innings_no", "player_key"),
         ((mk, no, player[p]) for no, p in f.absent_hurt))
    _ins(conn, "powerplays", ("match_key", "innings_no", "seq", "from_ball", "to_ball", "type"),
         ((mk,) + r for r in f.powerplays))
    _ins(conn, "miscounted_overs", ("match_key", "innings_no", "over_no", "balls"),
         ((mk,) + r for r in f.miscounted))
    conn.executemany(
        "INSERT INTO deliveries VALUES (%s)" % ", ".join("?" * 19),
        ((mk, no, ov, seq, label, player[b], player[ns], player[bw]) + tuple(rest)
         for no, ov, seq, label, b, ns, bw, *rest in f.deliveries))
    _ins(conn, "dismissals", ("match_key", "innings_no", "over_no", "seq", "wicket_seq",
                              "player_out_key", "kind", "bowler_key", "credited_to_bowler",
                              "counts_as_out"),
         ((mk, no, ov, seq, w, player[p], kind, player.get(bw), c, o)
          for no, ov, seq, w, p, kind, bw, c, o in f.dismissals))
    _ins(conn, "dismissal_fielders", ("match_key", "innings_no", "over_no", "seq", "wicket_seq",
                                      "fielder_seq", "player_key", "fielder_name", "is_substitute"),
         ((mk, no, ov, seq, w, fs, player.get(p), name, sub)
          for no, ov, seq, w, fs, p, name, sub in f.fielders))
    conn.executemany(
        "INSERT OR IGNORE INTO reviews (match_key, innings_no, over_no, seq, by_team_key, umpire,"
        " batter_key, decision, umpires_call, type) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ((mk, no, ov, seq, team.get(by) if by else None, ump, player.get(b), dec, uc, typ)
         for no, ov, seq, by, ump, b, dec, uc, typ in f.reviews))
    _ins(conn, "replacements", ("match_key", "innings_no", "over_no", "seq", "kind", "team_key",
                                "player_in_key", "player_out_key", "reason", "role"),
         ((mk, no, ov, seq, kind, team.get(t) if t else None, player.get(pi), player.get(po),
           reason, role) for no, ov, seq, kind, t, pi, po, reason, role in f.replacements))

    ctx = (m["format_key"], g, comp_key, m["season"], m["start_date"], venue_key)
    _ins(conn, "batting_innings", ("match_key", "innings_no", "player_key", "team_key",
                                   "opponent_key", "format_key", "gender", "competition_key",
                                   "season", "start_date", "venue_key", "batting_position", "runs",
                                   "balls_faced", "fours", "sixes", "is_out", "dismissal_kind",
                                   "is_super_over"),
         ((mk, b["innings_no"], player[b["player"]], team[b["team"]], team[b["opponent"]]) + ctx
          + (b["batting_position"], b["runs"], b["balls_faced"], b["fours"], b["sixes"],
             b["is_out"], b["dismissal_kind"], b["is_super_over"]) for b in f.batting))
    _ins(conn, "bowling_innings", ("match_key", "innings_no", "player_key", "team_key",
                                   "opponent_key", "format_key", "gender", "competition_key",
                                   "season", "start_date", "venue_key", "legal_balls",
                                   "runs_conceded", "wickets", "maidens", "wides", "noballs",
                                   "dots", "is_super_over"),
         ((mk, b["innings_no"], player[b["player"]], team[b["team"]], team[b["opponent"]]) + ctx
          + (b["legal_balls"], b["runs_conceded"], b["wickets"], b["maidens"], b["wides"],
             b["noballs"], b["dots"], b["is_super_over"]) for b in f.bowling))
    _ins(conn, "fielding_events", ("match_key", "innings_no", "player_key", "format_key",
                                   "catches", "stumpings", "run_outs", "as_substitute"),
         ((mk, r["innings_no"], player[r["player"]], m["format_key"], r["catches"],
           r["stumpings"], r["run_outs"], r["as_substitute"]) for r in f.fielding))
    _ins(conn, "phase_stats", ("match_key", "innings_no", "player_key", "phase", "format_key",
                               "competition_key", "season", "bat_runs", "bat_balls", "bat_outs",
                               "bowl_balls", "bowl_runs", "bowl_wkts"),
         ((mk, r["innings_no"], player[r["player"]], r["phase"], m["format_key"], comp_key,
           m["season"], r["bat_runs"], r["bat_balls"], r["bat_outs"], r["bowl_balls"],
           r["bowl_runs"], r["bowl_wkts"]) for r in f.phase_stats))
    _ins(conn, "team_results", ("match_key", "team_key", "opponent_key", "format_key", "gender",
                                "start_date", "venue_key", "competition_key", "outcome",
                                "margin_runs", "margin_wickets"),
         ((mk, team[r["team"]], team[r["opponent"]], m["format_key"], g, m["start_date"],
           venue_key, comp_key, r["outcome"], r["margin_runs"], r["margin_wickets"])
          for r in f.team_results))
    return mk


def delete_matches(conn: sqlite3.Connection, match_keys: List[int]) -> None:
    for i in range(0, len(match_keys), 500):
        chunk = match_keys[i:i + 500]
        marks = ", ".join("?" * len(chunk))
        for table in MATCH_TABLES:
            conn.execute("DELETE FROM %s WHERE match_key IN (%s)" % (table, marks), chunk)


def build_marts(conn: sqlite3.Connection) -> None:
    """Recompute player_career, player_year and player_teams from the atoms (marts.sql)."""
    with open(MARTS_SQL, encoding="utf-8") as f:
        conn.executescript(f.read())


def apply_venue_map(conn: sqlite3.Connection, rows: List[dict]) -> Dict[str, int]:
    """Set venues.country and canonical_venue_key from the reviewed map (sql/venue_map.csv:
    venue, city, canonical_venue, canonical_city, country), then home/away on team_results
    (F4 §2). Returns counts for the build summary."""
    conn.execute("UPDATE venues SET country = NULL, canonical_venue_key = venue_key")
    by_key = {(r["venue"], r["city"] or None): r for r in rows}
    venues = conn.execute("SELECT venue_key, name, city FROM venues").fetchall()
    index: Dict[str, List[Tuple[int, Optional[str]]]] = {}
    for key, name, city in venues:
        index.setdefault(name, []).append((key, city))
    mapped = 0
    for key, name, city in venues:
        r = by_key.get((name, city))
        if not r:
            continue
        mapped += 1
        canon = key
        cands = index.get(r["canonical_venue"] or name, [])
        want_city = r.get("canonical_city", city) or None
        if cands:
            canon = next((k for k, c in cands if c == want_city), cands[0][0])
        conn.execute("UPDATE venues SET country = ?, canonical_venue_key = ? WHERE venue_key = ?",
                     (r["country"] or None, canon, key))
    conn.execute(
        "UPDATE team_results SET home_away = ("
        " SELECT CASE WHEN v.country IS NULL OR t.team_type <> 'international' THEN NULL"
        "  WHEN v.country = t.name THEN 'home' WHEN v.country = o.name THEN 'away'"
        "  ELSE 'neutral' END"
        " FROM venues v, teams t, teams o WHERE v.venue_key = team_results.venue_key"
        " AND t.team_key = team_results.team_key AND o.team_key = team_results.opponent_key)")
    return {"venues": len(venues), "venues_mapped": mapped,
            "venues_unmapped": len(venues) - mapped}


def load_players(conn: sqlite3.Connection, people: Iterable[tuple], names: Iterable[tuple]) -> None:
    """Apply the Register to players seen in matches (people who never played, e.g. umpires, are
    left out), then rebuild external ids and names. people: (identifier, name, unique_name,
    {source: [ids]}); names: (identifier, name)."""
    ext, alias = [], []
    conn.executemany("UPDATE players SET name = ?, unique_name = ? WHERE player_id = ?",
                     ((name, unique_name, ident) for ident, name, unique_name, _ in people))
    for ident, name, unique_name, ids in people:
        for source, values in ids.items():
            ext += [(ident, source, v) for v in values]
        alias += [(ident, name, "register"), (ident, unique_name, "register_unique")]
    alias += [(ident, name, "register_variant") for ident, name in names]
    conn.execute("DELETE FROM player_external_ids")
    conn.execute("DELETE FROM player_names")
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS _ext (player_id TEXT, source TEXT, ext TEXT)")
    conn.execute("DELETE FROM _ext")
    conn.executemany("INSERT INTO _ext VALUES (?,?,?)", ext)
    conn.execute("INSERT OR IGNORE INTO player_external_ids SELECT p.player_key, e.source, e.ext"
                 " FROM _ext e JOIN players p USING (player_id)")
    conn.execute("DROP TABLE _ext")
    refresh_player_names(conn, alias)


def refresh_player_names(conn: sqlite3.Connection, alias: List[tuple]) -> None:
    """player_names = Register names and variants, every player's own name, plus derived
    surname aliases (the basis for "did you mean…")."""
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS _alias (player_id TEXT, name TEXT, source TEXT)")
    conn.execute("DELETE FROM _alias")
    conn.executemany("INSERT INTO _alias VALUES (?,?,?)", alias)
    conn.execute("INSERT OR IGNORE INTO player_names SELECT p.player_key, a.name, a.source"
                 " FROM _alias a JOIN players p USING (player_id)")
    conn.execute("INSERT OR IGNORE INTO player_names SELECT player_key, name, 'scorecard'"
                 " FROM players")
    surnames = []
    for key, name in conn.execute("SELECT player_key, name FROM player_names").fetchall():
        parts = name.split()
        if len(parts) > 1 and len(parts[-1]) > 1:
            surnames.append((key, parts[-1], "derived_surname"))
    conn.executemany("INSERT OR IGNORE INTO player_names VALUES (?,?,?)", surnames)
    conn.execute("DROP TABLE _alias")


def measure(conn: sqlite3.Connection) -> Dict[str, object]:
    """Counts the quality checks need (application-logic/quality/build_checks.py)."""
    one = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    d = conn.execute(
        "SELECT COUNT(*), SUM(runs_batter), SUM(runs_batter + wides + noballs), SUM(is_legal),"
        " SUM(runs_total <> runs_batter + runs_extras"
        "     OR runs_extras <> wides + noballs + byes + legbyes + penalty)"
        " FROM deliveries").fetchone()
    return {
        "quick_check": one("PRAGMA quick_check"),
        "matches": one("SELECT COUNT(*) FROM matches"),
        "played_matches": one("SELECT COUNT(*) FROM matches WHERE has_deliveries = 1"),
        "deliveries": d[0],
        "delivery_runs_mismatch": d[4] or 0,
        "innings_total_mismatch": one(
            "SELECT COUNT(*) FROM innings i LEFT JOIN (SELECT match_key, innings_no,"
            " SUM(runs_total) AS s FROM deliveries GROUP BY match_key, innings_no) d"
            " USING (match_key, innings_no)"
            " WHERE i.total_runs <> COALESCE(d.s, 0) + i.penalty_runs_pre + i.penalty_runs_post"),
        "fk_violations": len(conn.execute("PRAGMA foreign_key_check").fetchall()),
        "played_without_two_results": one(
            "SELECT COUNT(*) FROM matches m WHERE m.has_deliveries = 1 AND"
            " (SELECT COUNT(*) FROM team_results r WHERE r.match_key = m.match_key) <> 2"),
        "bat_runs_diff": (one("SELECT COALESCE(SUM(runs), 0) FROM batting_innings")
                          - (d[1] or 0)),
        "bowl_runs_diff": (one("SELECT COALESCE(SUM(runs_conceded), 0) FROM bowling_innings")
                           - (d[2] or 0)),
        "bowl_balls_diff": (one("SELECT COALESCE(SUM(legal_balls), 0) FROM bowling_innings")
                            - (d[3] or 0)),
        "bowl_wkts_diff": (one("SELECT COALESCE(SUM(wickets), 0) FROM bowling_innings")
                           - one("SELECT COUNT(*) FROM dismissals WHERE credited_to_bowler = 1")),
        "atoms_off_team_sheet": one(
            "SELECT COUNT(*) FROM (SELECT match_key, player_key FROM batting_innings UNION"
            " SELECT match_key, player_key FROM bowling_innings) a"
            " WHERE NOT EXISTS (SELECT 1 FROM match_players mp WHERE mp.match_key = a.match_key"
            " AND mp.player_key = a.player_key)"),
        "player_career": one("SELECT COUNT(*) FROM player_career"),
        "players_in_both_genders": [r[0] for r in conn.execute(
            "SELECT p.player_id FROM match_players mp JOIN matches m USING (match_key)"
            " JOIN players p USING (player_key) GROUP BY p.player_id"
            " HAVING COUNT(DISTINCT m.gender) > 1 ORDER BY p.player_id")],
    }


def row_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        " ORDER BY name")]
    return {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in tables}
