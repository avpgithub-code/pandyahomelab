"""Players endpoints, checked against the serving DB the pipeline built."""
import sqlite3

import pytest

from tests.conftest import pid

KOHLI = pid("V Kohli")


@pytest.fixture(scope="module")
def db(home):
    c = sqlite3.connect("file:%s?mode=ro" % (home / "data" / "db" / "cricstat.sqlite"), uri=True)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def data(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_profile(client):
    p = data(client, "/v1/players/%s" % KOHLI)
    assert p["name"] == "V Kohli" and p["slug"] == "v-kohli-%s" % KOHLI
    assert p["gender"] == "male" and p["main_team"]["slug"] == "india-men"
    assert {t["slug"] for t in p["teams"]} == {"india-men", "mumbai-indians-men"}
    assert {s["scope"] for s in p["scopes"]} >= {"ALL", "ODI", "T20I", "TEST", "ipl", "LEAGUES"}
    assert p["role"] in ("batter", "bowler", "all-rounder", "wicketkeeper")
    assert p["bio"]["date_of_birth"] is None                 # Wikidata enrichment comes later


def test_career_matches_the_views(client, db):
    c = data(client, "/v1/players/%s/career?scope=ODI" % KOHLI)
    v = db.execute("SELECT * FROM v_player_batting WHERE player_id = ? AND scope = 'ODI'",
                   (KOHLI,)).fetchone()
    assert c["matches"] == 3 and c["batting"]["runs"] == v["runs"]
    assert c["batting"]["average"] == pytest.approx(v["average"])
    assert c["batting"]["high_score_not_out"] in (True, False)
    assert c["fielding"]["notes"]["run_out_involvements"].startswith("Not an official")


@pytest.mark.parametrize("scope", ["ALL", "ODI", "T20I", "TEST", "ipl", "LEAGUES"])
def test_scope_filter_selects_the_same_matches_as_the_marts(client, db, scope):
    """The API's scope SQL (atoms) must pick exactly the matches player_career counted."""
    rows = data(client, "/v1/players/%s/innings?scope=%s&limit=100" % (KOHLI, scope))
    career = db.execute("SELECT c.matches FROM player_career c JOIN players p USING (player_key)"
                        " WHERE p.player_id = ? AND c.scope = ?", (KOHLI, scope)).fetchone()
    assert len(rows) == career["matches"]


def test_years_sum_to_career_and_ratios_match_formula(client):
    years = data(client, "/v1/players/%s/years?scope=ALL" % KOHLI)
    career = data(client, "/v1/players/%s/career?scope=ALL" % KOHLI)
    assert sum(y["runs"] for y in years) == career["batting"]["runs"]
    for y in years:
        outs = y["bat_innings"] - y["not_outs"]
        assert y["average"] == (pytest.approx(y["runs"] / outs) if outs else None)


def test_phases_agree_with_the_phase_view(client, db):
    rows = data(client, "/v1/players/%s/phases?scope=T20I" % KOHLI)
    view = {r["phase"]: r for r in db.execute(
        "SELECT * FROM v_player_phase v JOIN players p USING (player_key)"
        " WHERE p.player_id = ? AND v.format_key = 'T20I'", (KOHLI,))}
    assert rows and {r["phase"] for r in rows} == set(view)
    for r in rows:
        assert r["bat_runs"] == view[r["phase"]]["bat_runs"]
        assert r["bat_strike_rate"] == pytest.approx(view[r["phase"]]["bat_strike_rate"])
        assert r["label"].startswith(("Powerplay", "Middle", "Death"))
    assert data(client, "/v1/players/%s/phases?scope=ipl" % KOHLI)


def test_splits(client):
    s = data(client, "/v1/players/%s/splits?by=opponent&scope=ODI" % KOHLI)
    assert [r["label"] for r in s["batting"]] == ["Australia"]
    assert s["batting"][0]["slug"] == "australia-men"
    v = data(client, "/v1/players/%s/splits?by=venue&scope=ODI" % KOHLI)
    assert {r["label"] for r in v["batting"]} <= {"Wankhede Stadium, Mumbai",
                                                  "Melbourne Cricket Ground"}
    assert client.get("/v1/players/%s/splits?by=moon" % KOHLI).status_code == 400


def test_innings_paging_and_dates(client):
    first = client.get("/v1/players/%s/innings?scope=ALL&limit=2" % KOHLI).json()
    assert len(first["data"]) == 2 and first["meta"]["next"].endswith("offset=2")
    rest = client.get(first["meta"]["next"]).json()
    assert {r["match_id"] for r in rest["data"]}.isdisjoint(r["match_id"] for r in first["data"])
    y2024 = data(client, "/v1/players/%s/innings?scope=ODI&from=2024&to=2024" % KOHLI)
    assert {r["match_id"] for r in y2024} == {"9001", "9002"}
    assert data(client, "/v1/players/%s/innings?scope=ODI&from=2024-25&to=2024-25" % KOHLI) == [
        r for r in data(client, "/v1/players/%s/innings?scope=ODI" % KOHLI)
        if r["match_id"] == "9007"]


def test_search(client):
    s = data(client, "/v1/search?q=kohli")
    assert s["players"][0]["player_id"] == KOHLI and s["players"][0]["main_team"] == "India"
    assert data(client, "/v1/search?q=IndW&type=player&gender=female")["players"]
    assert data(client, "/v1/search?q=IndW&type=player&gender=male")["players"] == []
    teams = data(client, "/v1/search?q=ind&type=team")["teams"]
    assert teams[0]["slug"] in ("india-men", "india-women")
    comps = data(client, "/v1/search?q=premier&type=competition")["competitions"]
    assert comps[0]["competition_slug"] == "ipl"
