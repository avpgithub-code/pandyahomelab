"""Head to Head endpoints (docs/h2h-plan.md), checked against the deliveries in the serving DB the
pipeline built: every matchup number must equal the same count taken straight from the balls."""
import sqlite3

import pytest

from tests.conftest import pid

KOHLI, INDIA_WOMAN = pid("V Kohli"), pid("IndW 1")


@pytest.fixture(scope="module")
def db(home):
    c = sqlite3.connect("file:%s?mode=ro" % (home / "data" / "db" / "cricstat.sqlite"), uri=True)
    yield c
    c.close()


@pytest.fixture(scope="module")
def pair(db):
    """The batter v bowler pair with the most ODI balls in the fixture (player ids)."""
    return db.execute(
        "SELECT a.player_id, b.player_id FROM matchups u"
        " JOIN players a ON a.player_key = u.batter_key"
        " JOIN players b ON b.player_key = u.bowler_key WHERE u.scope = 'ODI'"
        " ORDER BY u.balls DESC, a.player_id LIMIT 1").fetchone()


@pytest.fixture(scope="module")
def busy_bowler(db):
    """The ODI bowler who bowled to the most different batters."""
    return db.execute(
        "SELECT p.player_id FROM matchups u JOIN players p ON p.player_key = u.bowler_key"
        " WHERE u.scope = 'ODI' GROUP BY p.player_id ORDER BY COUNT(*) DESC, p.player_id"
        " LIMIT 1").fetchone()[0]


def data(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def from_balls(db, scope, batter, bowler):
    """(balls, runs, outs) for a batter v bowler straight from deliveries and dismissals."""
    key = lambda p: db.execute("SELECT player_key FROM players WHERE player_id = ?",  # noqa: E731
                               (p,)).fetchone()[0]
    a, b = key(batter), key(bowler)
    balls, runs = db.execute(
        "SELECT SUM(d.wides = 0), SUM(d.runs_batter) FROM deliveries d JOIN matches m"
        " USING (match_key) WHERE m.format_key = ? AND d.batter_key = ? AND d.bowler_key = ?",
        (scope, a, b)).fetchone()
    outs = db.execute(
        "SELECT COUNT(*) FROM dismissals x JOIN matches m USING (match_key) WHERE m.format_key = ?"
        " AND x.player_out_key = ? AND x.bowler_key = ? AND x.credited_to_bowler = 1",
        (scope, a, b)).fetchone()[0]
    return balls or 0, runs or 0, outs


@pytest.mark.parametrize("scope", ["ODI", "TEST", "T20I"])
def test_matchup_equals_the_balls(client, db, pair, scope):
    d = data(client, "/v1/h2h/players/%s/%s?scope=%s" % (pair[0], pair[1], scope))
    m = d["matchup"]["a_batting"]
    want = from_balls(db, scope, pair[0], pair[1])
    if want[0] == 0:
        assert m is None
        return
    assert (m["balls"], m["runs"], m["outs"]) == want
    assert m["strike_rate"] == pytest.approx(m["runs"] * 100 / m["balls"])
    assert m["average"] == (pytest.approx(m["runs"] / m["outs"]) if m["outs"] else None)
    assert m["small_sample"] == (m["balls"] < 30)
    assert sum(k["n"] for k in m["dismissals"]) == m["outs"]


def test_both_sides_carry_their_careers(client, pair):
    d = data(client, "/v1/h2h/players/%s/%s?scope=ODI" % pair)
    assert (d["a"]["player"]["player_id"], d["b"]["player"]["player_id"]) == tuple(pair)
    career = data(client, "/v1/players/%s/career?scope=ODI" % pair[0])
    assert d["a"]["batting"] == career["batting"]
    assert [f["scope"] for f in d["formats"]] == ["ODI", "TEST", "T20I"]
    assert d["formats"][0]["balls_between"] > 0


def test_the_other_direction_is_the_mirror(client, pair):
    d = data(client, "/v1/h2h/players/%s/%s?scope=ODI" % (pair[0], pair[1]))
    flip = data(client, "/v1/h2h/players/%s/%s?scope=ODI" % (pair[1], pair[0]))
    assert d["matchup"]["a_batting"] and d["matchup"]["a_batting"] == flip["matchup"]["b_batting"]


def test_opponents_rank_by_balls(client, db, busy_bowler):
    rows = data(client, "/v1/h2h/opponents/%s?scope=ODI&as=bowler" % busy_bowler)
    assert len(rows) >= 2
    assert [r["balls"] for r in rows] == sorted((r["balls"] for r in rows), reverse=True)
    assert all(r["roles"] == ["bowler"] for r in rows)
    top = rows[0]
    assert (top["balls"], top["runs"], top["outs"]) == from_balls(db, "ODI", top["player_id"],
                                                                  busy_bowler)
    assert len(data(client, "/v1/h2h/opponents/%s?scope=ODI&limit=1" % busy_bowler)) == 1


@pytest.mark.parametrize("url,status", [
    ("/v1/h2h/players/%s/%s" % (KOHLI, KOHLI), 400),                     # same player
    ("/v1/h2h/players/%s/ffffffff" % KOHLI, 404),                        # unknown player
    ("/v1/h2h/players/%s/%s?scope=ipl" % (KOHLI, pid("AusM 1")), 400),      # internationals only
    ("/v1/h2h/players/%s/%s" % (KOHLI, INDIA_WOMAN), 422),               # man v woman
    ("/v1/h2h/opponents/%s?as=keeper" % KOHLI, 400),
])
def test_bad_requests_are_problem_json(client, url, status):
    r = client.get(url)
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith("application/problem+json")


def test_team_results_filter_by_opponent(client):
    every = data(client, "/v1/teams/india-men/results?limit=100")
    only = data(client, "/v1/teams/india-men/results?opponent=australia-men&limit=100")
    assert only and all(r["opponent"]["slug"] == "australia-men" for r in only)
    assert len(only) == sum(r["opponent"]["slug"] == "australia-men" for r in every)
    assert client.get("/v1/teams/india-men/results?opponent=nowhere-men").status_code == 404


@pytest.mark.parametrize("scope", ["ODI", "TEST", "T20I"])
def test_dismissal_list_adds_up_to_the_outs(client, pair, scope):
    m = data(client, "/v1/h2h/players/%s/%s?scope=%s" % (pair[0], pair[1], scope))["matchup"]
    rows = data(client, "/v1/h2h/dismissals/%s/%s?scope=%s" % (pair[0], pair[1], scope))
    outs = m["a_batting"]["outs"] if m["a_batting"] else 0
    assert len(rows) == outs
    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        assert r["outcome"] in ("won", "lost", "drawn", "tied", "no result")
        assert " b " in r["how"] or r["how"].startswith("c & b ")
        assert r["score"]["balls"] is not None
    want = (m["a_batting"] or {"dismissals": []})["dismissals"]
    assert kinds == {k["kind"]: k["n"] for k in want}
    assert [r["date"] for r in rows] == sorted(r["date"] for r in rows)
