"""Head to Head matchups (docs/h2h-plan.md): batter v bowler counts built from the deliveries,
and the build checks that prove they add up to the batting atoms and the credited dismissals."""
import sqlite3

from db_logic.repository import serving_store
from tests.serving.conftest import CASES, case_doc, pid

CASE = {c["id"][:3]: c for c in CASES["delivery_cases"]}


def _pair(conn, batter, bowler, scope="ODI"):
    cur = conn.execute(
        "SELECT u.* FROM matchups u JOIN players a ON a.player_key = u.batter_key"
        " JOIN players b ON b.player_key = u.bowler_key"
        " WHERE u.scope = ? AND a.player_id = ? AND b.player_id = ?",
        (scope, pid(batter), pid(bowler)))
    row = cur.fetchone()
    return dict(zip([d[0] for d in cur.description], row)) if row else None


def test_extras_follow_the_balls_faced_and_boundary_rules(build_env):
    conn, summary = build_env({"1": case_doc(CASE["C1_"])})
    assert summary["status"] == "success", summary
    a = _pair(conn, "A", "B1")
    # wide not faced (R3); the no-ball is faced and its 4 off the bat counts; byes/leg-byes are dots
    got = (a["balls"], a["runs"], a["dots"], a["fours"], a["sixes"], a["outs"])
    assert got == (5, 5, 3, 1, 0, 0)
    assert a["matches"] == 1 and a["first_date"] == a["last_date"] == "2026-01-01"
    n = _pair(conn, "N", "B1")
    assert (n["balls"], n["runs"], n["dots"]) == (2, 0, 2)


def test_only_dismissals_credited_to_the_bowler_are_outs(build_env):
    conn, _ = build_env({"1": case_doc(CASE["C6_"]),
                         "2": case_doc(CASE["C5_"], start_date="2026-01-02")})
    assert _pair(conn, "A", "B1")["outs"] == 1          # caught and bowled
    assert _pair(conn, "N", "B1")["outs"] == 1          # caught by a substitute still credits B1
    kinds = dict(conn.execute(
        "SELECT o.kind, o.n FROM matchup_outs o JOIN players p ON p.player_key = o.batter_key"
        " WHERE p.player_id = ?", (pid("A"),)).fetchall())
    assert kinds == {"caught and bowled": 1}
    # C5: the non-striker's run out is nobody's matchup out, but A's single still counts
    assert _pair(conn, "A", "B1")["runs"] == 1 and _pair(conn, "A", "B1")["matches"] == 2


def test_non_boundary_four_is_runs_not_a_four(build_env):
    conn, _ = build_env({"1": case_doc(CASE["C9_"])})
    a = _pair(conn, "A", "B1")
    assert (a["runs"], a["fours"], a["balls"]) == (4, 0, 2)


def test_matchups_add_up_and_skip_super_overs_and_leagues(build_env):
    docs = {str(i): case_doc(CASE[k], start_date="2026-01-%02d" % i)
            for i, k in enumerate(["C1_", "C4_", "C5_", "C6_", "C7_", "C8_", "C9_"], start=1)}
    conn, summary = build_env(docs)
    assert summary["status"] == "success", summary
    m = serving_store.measure(conn)
    assert m["matchup_bat_diff"] == 0 and m["matchup_outs_diff"] == 0
    scopes = {r[0] for r in conn.execute("SELECT DISTINCT scope FROM matchups")}
    assert scopes <= {"TEST", "ODI", "T20I"} and "HUNDRED" not in scopes


def test_a_broken_matchup_fails_the_build_checks(build_env):
    from application_logic.quality import build_checks

    conn, _ = build_env({"1": case_doc(CASE["C1_"])})
    path = conn.execute("PRAGMA database_list").fetchone()[2]
    rw = sqlite3.connect(path)
    rw.execute("UPDATE matchups SET runs = runs + 1")
    rw.commit()
    m = dict(serving_store.measure(rw), raw_active=1)     # raw_active comes from the build itself
    failures, _ = build_checks.evaluate(m)
    assert any("matchup balls or runs" in f for f in failures)
    rw.close()
