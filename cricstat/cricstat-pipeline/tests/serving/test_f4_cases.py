"""F4 metric cases, end to end: each fixture match goes raw store → build → serving DB, and the
counts the build stores (atoms, innings, marts, team results) must equal the fixture's expectations.
The aggregation cases (A1, A2) feed atoms straight into the mart SQL.
"""
import sqlite3

import pytest

from db_logic.repository import serving_store
from tests.serving.conftest import CASES, SQL_DIR, case_doc, pid

DELIVERY = {c["id"]: c for c in CASES["delivery_cases"]}
AGG = {c["id"]: c for c in CASES["aggregation_cases"]}
SCOPE = {"ODI": "ODI", "T20": "T20I", "HUNDRED": "HUNDRED", "TEST": "TEST"}


def _row(conn, sql, args):
    cur = conn.execute(sql, args)
    row = cur.fetchone()
    return dict(zip([d[0] for d in cur.description], row)) if row else None


def _player_row(conn, table, name, extra=""):
    return _row(conn, "SELECT t.* FROM %s t JOIN players p USING (player_key) "
                      "WHERE p.player_id = ? %s" % (table, extra), (pid(name),))


def _check(actual, expected, label):
    assert actual is not None, "%s: no row" % label
    for key, want in expected.items():
        if isinstance(want, float):
            want = pytest.approx(want)
        assert actual[key] == want, "%s.%s" % (label, key)


@pytest.mark.parametrize("case_id", sorted(DELIVERY))
def test_delivery_case(build_env, case_id):
    case = DELIVERY[case_id]
    conn, summary = build_env({"9%s" % case_id[1:].split("_")[0]: case_doc(case)})
    assert summary["status"] == "success", summary
    e = case["expect"]
    not_super = "AND t.is_super_over = 0"

    for name, want in e.get("batting", {}).items():
        _check(_player_row(conn, "batting_innings", name, not_super), want, "batting " + name)
    for name, want in e.get("bowling", {}).items():
        want = dict(want)
        economy = want.pop("economy", None)
        _check(_player_row(conn, "bowling_innings", name, not_super), want, "bowling " + name)
        if economy is not None:
            got = _row(conn, "SELECT economy FROM v_player_bowling"
                             " WHERE player_id = ? AND scope = ?",
                       (pid(name), SCOPE[case["format"]]))
            assert got["economy"] == pytest.approx(economy)
    for name, want in e.get("fielding", {}).items():
        want = {("as_substitute" if k == "catches_as_substitute" else k): v
                for k, v in want.items()}
        _check(_player_row(conn, "fielding_events", name), want, "fielding " + name)
    if "innings" in e:
        first = _row(conn, "SELECT * FROM innings WHERE innings_no = 1", ())
        _check(first, e["innings"], "innings")
    for name, want in e.get("career_batting", {}).items():
        got = _row(conn, "SELECT c.* FROM player_career c JOIN players p USING (player_key) "
                         "WHERE p.player_id = ? AND c.scope = ?",
                   (pid(name), SCOPE[case["format"]]))
        _check(got, want, "career " + name)
    for team, want in e.get("team_results", {}).items():
        got = _row(conn, "SELECT r.outcome FROM team_results r JOIN teams t USING (team_key) "
                         "WHERE t.name = ?", (team,))
        _check(got, want, "team_results " + team)
    if "match" in e:
        m = _row(conn, "SELECT m.result, m.decided_by, m.has_deliveries, w.name AS winner "
                       "FROM matches m LEFT JOIN teams w ON w.team_key = m.winner_key", ())
        _check(m, e["match"], "match")
    if "team_results_rows" in e:
        assert conn.execute("SELECT COUNT(*) FROM team_results").fetchone()[0] == \
            e["team_results_rows"]
    if "match_players_counted" in e:
        counted = conn.execute("SELECT COALESCE(SUM(matches), 0) FROM player_career "
                               "WHERE scope = ?", (SCOPE[case["format"]],)).fetchone()[0]
        assert counted == e["match_players_counted"]
        assert conn.execute("SELECT COUNT(*) FROM match_players").fetchone()[0] > 0


@pytest.fixture()
def mart_db():
    """Schema + reference data, one player and one match, ready for hand-written atoms."""
    con = sqlite3.connect(":memory:")
    serving_store.create_schema(con, str(SQL_DIR))
    con.execute("INSERT INTO players (player_key, player_id, name, unique_name)"
                " VALUES (1, 'aaaaaaaa', 'P One', 'P One')")
    yield con
    con.close()


def _atom(con, table, i, **cols):
    base = dict(match_key=i, innings_no=1, player_key=1, team_key=1, opponent_key=2,
                format_key="ODI", gender="male", competition_key=None, season="2026",
                start_date="2026-01-%02d" % i, venue_key=1, is_super_over=0)
    base.update(cols)
    con.execute("INSERT INTO %s (%s) VALUES (%s)" % (table, ", ".join(base),
                                                     ", ".join("?" * len(base))),
                list(base.values()))


def _career(con):
    serving_store.build_marts(con)
    return _row(con, "SELECT * FROM player_career WHERE scope = 'ODI'", ())


def _prepare(con, n):
    con.execute("INSERT INTO teams VALUES (1, 'Home', 'male', 'international'),"
                " (2, 'Away', 'male', 'international')")
    con.execute("INSERT INTO venues (venue_key, name, city) VALUES (1, 'Ground', 'City')")
    for i in range(1, n + 1):
        con.execute(
            "INSERT INTO matches (match_key, match_id, match_type, team_type, gender,"
            " balls_per_over, format_key, season, start_date, end_date, n_days, venue_key,"
            " team1_key, team2_key, result, has_deliveries, source_sha256)"
            " VALUES (?, ?, 'ODI', 'international', 'male', 6, 'ODI', '2026', ?, ?, 1, 1, 1, 2,"
            " 'no_result', 1, 'x')", (i, str(i), "2026-01-%02d" % i, "2026-01-%02d" % i))
        con.execute("INSERT INTO match_players VALUES (?, 1, 1, 'xi')", (i,))


def test_a1_batting_milestones(mart_db):
    case = AGG["A1_batting_milestones"]
    _prepare(mart_db, len(case["innings"]))
    for i, inn in enumerate(case["innings"], start=1):
        _atom(mart_db, "batting_innings", i, batting_position=1, runs=inn["runs"],
              balls_faced=inn["balls_faced"], fours=0, sixes=0, is_out=inn["is_out"])
    got = _career(mart_db)
    want = {k: v for k, v in case["expect"].items() if k not in ("average", "strike_rate")}
    _check(got, want, "A1")
    avg, sr = mart_db.execute("SELECT average, strike_rate FROM v_player_batting "
                              "WHERE scope = 'ODI'").fetchone()
    assert avg == pytest.approx(case["expect"]["average"], abs=1e-4)
    assert sr == pytest.approx(case["expect"]["strike_rate"], abs=1e-4)


def test_a2_bowling_best_and_ratios(mart_db):
    case = AGG["A2_bowling_best_and_ratios"]
    _prepare(mart_db, len(case["innings"]))
    for i, inn in enumerate(case["innings"], start=1):
        _atom(mart_db, "bowling_innings", i, legal_balls=inn["legal_balls"],
              runs_conceded=inn["runs_conceded"], wickets=inn["wickets"], maidens=0, wides=0,
              noballs=0, dots=0)
    _career(mart_db)
    e = case["expect"]
    got = _row(mart_db, "SELECT * FROM v_player_bowling WHERE scope = 'ODI'", ())
    for key in ("legal_balls", "runs_conceded", "wickets", "best_bowling_wkts",
                "best_bowling_runs", "four_wkt_hauls", "five_wkt_hauls", "overs_display"):
        assert got[key] == e[key], key
    for key in ("average", "economy", "strike_rate"):
        assert got[key] == pytest.approx(e[key], abs=1e-4), key


def test_a3_team_win_pct_uses_built_team_results(build_env):
    case = AGG["A3_team_win_pct"]
    outcomes = {"won": {"winner": "Home", "by": {"runs": 1}},
                "lost": {"winner": "Away", "by": {"runs": 1}},
                "tied": {"result": "tie"}, "no_result": {"result": "no result"}}
    base = DELIVERY["C9_penalty_and_non_boundary"]
    docs = {}
    for i, res in enumerate(case["results"], start=1):
        docs[str(100 + i)] = case_doc(dict(base, outcome=outcomes[res]),
                                      start_date="2026-02-%02d" % i)
    conn, _ = build_env(docs)
    row = _row(conn, "SELECT matches, won, lost, tied, no_result, win_pct FROM v_team_record "
                     "WHERE team = 'Home'", ())
    _check(row, case["expect"], "A3")
