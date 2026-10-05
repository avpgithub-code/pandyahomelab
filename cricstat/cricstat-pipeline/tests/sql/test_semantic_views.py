"""F4 checks: serving schema, reference rules and semantic views load together and compute ratios.

The build step that turns deliveries into counts does not exist yet. These tests feed the views
the expected counts from tests/fixtures/f4_metric_cases.json, then check the derived ratios and
the rule tables.
"""

import json
import sqlite3
from pathlib import Path

import pytest

CRICSTAT = Path(__file__).resolve().parents[3]
SQL = CRICSTAT / "sql"
CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "f4_metric_cases.json").read_text()
)
AGG = {c["id"]: c for c in CASES["aggregation_cases"]}

KINDS_IN_DATA = {  # all 14 dismissal kinds found when profiling raw.sqlite on 2026-10-05
    "caught",
    "bowled",
    "lbw",
    "caught and bowled",
    "run out",
    "stumped",
    "hit wicket",
    "retired hurt",
    "retired not out",
    "obstructing the field",
    "retired out",
    "handled the ball",
    "timed out",
    "hit the ball twice",
}


@pytest.fixture()
def db():
    con = sqlite3.connect(":memory:")
    for name in ("serving_schema.sql", "reference_data.sql", "semantic_views.sql"):
        con.executescript((SQL / name).read_text())
    con.execute(
        "INSERT INTO players (player_key, player_id, name, unique_name)"
        " VALUES (1, 'aaaaaaaa', 'P One', 'P One')"
    )
    yield con
    con.close()


def career_row(con, **counts):
    cols = ["player_key", "scope", "gender", "matches"] + list(counts)
    vals = [1, "ODI", "male", 5] + list(counts.values())
    con.execute(
        "INSERT INTO player_career (%s) VALUES (%s)"
        % (", ".join(cols), ", ".join("?" * len(vals))),
        vals,
    )


def test_every_dismissal_kind_is_classified(db):
    kinds = {r[0] for r in db.execute("SELECT kind FROM dismissal_kinds")}
    assert kinds == KINDS_IN_DATA


def test_bowler_credit_and_out_rules(db):
    rows = dict(
        (
            (k, (b, o))
            for k, b, o in db.execute(
                "SELECT kind, credited_to_bowler, counts_as_out FROM dismissal_kinds"
            )
        )
    )
    assert rows["run out"] == (0, 1)
    assert rows["caught and bowled"] == (1, 1)
    assert rows["retired hurt"] == (0, 0)
    assert rows["retired not out"] == (0, 0)
    assert rows["retired out"] == (0, 1)


def test_phases_are_contiguous_and_cover_the_innings(db):
    expected_last = {"t20": 19, "one_day": 49, "hundred": 19}
    for family, last in expected_last.items():
        ranges = db.execute(
            "SELECT from_over, to_over FROM phase_defs WHERE format_family = ? ORDER BY from_over",
            (family,),
        ).fetchall()
        assert ranges[0][0] == 0 and ranges[-1][1] == last
        for (_, prev_to), (nxt_from, _) in zip(ranges, ranges[1:]):
            assert nxt_from == prev_to + 1


def test_hundred_is_its_own_format(db):
    row = db.execute(
        "SELECT format_key, format_family FROM format_map"
        " WHERE match_type='T20' AND team_type='club' AND balls_per_over=5"
    ).fetchone()
    assert row == ("HUNDRED", "hundred")


def test_batting_ratios(db):
    e = AGG["A1_batting_milestones"]["expect"]
    career_row(
        db,
        bat_innings=e["bat_innings"],
        not_outs=e["not_outs"],
        runs=e["runs"],
        balls_faced=e["balls_faced"],
        high_score=e["high_score"],
        high_score_not_out=e["high_score_not_out"],
        hundreds=e["hundreds"],
        fifties=e["fifties"],
        ducks=e["ducks"],
        fours=0,
        sixes=0,
    )
    avg, sr = db.execute("SELECT average, strike_rate FROM v_player_batting").fetchone()
    assert avg == pytest.approx(e["average"], abs=1e-4)
    assert sr == pytest.approx(e["strike_rate"], abs=1e-4)


def test_batting_average_is_null_without_dismissals(db):
    career_row(db, bat_innings=2, not_outs=2, runs=30, balls_faced=20)
    assert db.execute("SELECT average FROM v_player_batting").fetchone()[0] is None


def test_bowling_ratios_and_overs_display(db):
    e = AGG["A2_bowling_best_and_ratios"]["expect"]
    career_row(
        db,
        bowl_innings=4,
        legal_balls=e["legal_balls"],
        runs_conceded=e["runs_conceded"],
        wickets=e["wickets"],
        maidens=0,
        best_bowling_wkts=e["best_bowling_wkts"],
        best_bowling_runs=e["best_bowling_runs"],
        four_wkt_hauls=e["four_wkt_hauls"],
        five_wkt_hauls=e["five_wkt_hauls"],
    )
    overs, avg, econ, sr = db.execute(
        "SELECT overs_display, average, economy, strike_rate FROM v_player_bowling"
    ).fetchone()
    assert overs == e["overs_display"]
    assert avg == pytest.approx(e["average"], abs=1e-4)
    assert econ == pytest.approx(e["economy"], abs=1e-4)
    assert sr == pytest.approx(e["strike_rate"], abs=1e-4)


def test_hundred_economy_is_per_six_balls(db):
    career_row(db, bowl_innings=1, legal_balls=10, runs_conceded=12, wickets=0)
    assert db.execute("SELECT economy FROM v_player_bowling").fetchone()[0] == pytest.approx(7.2)


def test_team_win_pct_excludes_no_results_only(db):
    case = AGG["A3_team_win_pct"]
    db.execute(
        "INSERT INTO teams (team_key, name, gender, team_type) VALUES"
        " (1, 'India', 'male', 'international'), (2, 'Opp', 'male', 'international')"
    )
    for i, outcome in enumerate(case["results"], start=1):
        db.execute(
            "INSERT INTO team_results (match_key, team_key, opponent_key, format_key, gender,"
            " start_date, venue_key, outcome)"
            " VALUES (?, 1, 2, 'ODI', 'male', '2026-01-0%d', 1, ?)" % i,
            (i, outcome),
        )
    row = db.execute(
        "SELECT matches, won, lost, tied, no_result, win_pct FROM v_team_record WHERE team_key = 1"
    ).fetchone()
    e = case["expect"]
    assert row == (
        e["matches"],
        e["won"],
        e["lost"],
        e["tied"],
        e["no_result"],
        pytest.approx(e["win_pct"]),
    )


def test_fixture_cases_are_well_formed():
    ids = [c["id"] for c in CASES["delivery_cases"] + CASES["aggregation_cases"]]
    assert len(ids) == len(set(ids)) == 13
    for c in CASES["delivery_cases"]:
        assert c["rules"] and c["expect"] and c["format"]
