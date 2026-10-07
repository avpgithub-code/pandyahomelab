"""Match list with scores, team results with scores, and leaderboards."""
import pytest

from application_logic.services.matches_service import score_line


def data(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("inn,want", [
    ({"runs": 287, "wickets": 6, "legal_balls": 300, "declared": 0}, "287/6 (50 ov)"),
    ({"runs": 142, "wickets": 10, "legal_balls": 223, "declared": 0}, "142 (37.1 ov)"),
    ({"runs": 350, "wickets": 8, "legal_balls": 600, "declared": 1}, "350/8d (100 ov)"),
    ({"runs": 160, "wickets": 4, "legal_balls": 98, "declared": 0, "balls_per_over": 5},
     "160/4 (19.3 ov)")])
def test_score_line(inn, want):
    assert score_line(inn) == want


def test_matches_newest_first_with_both_scores(client):
    body = data(client, "/v1/matches?gender=male&limit=3")
    rows = body["data"]
    assert [r["date"] for r in rows] == sorted((r["date"] for r in rows), reverse=True)
    m = rows[0]
    assert len(m["teams"]) == 2 and all(t["slug"] for t in m["teams"])
    assert all(t["innings"] for t in m["teams"]) and body["meta"]["next"]


def test_matches_filters(client):
    women = data(client, "/v1/matches?gender=female")["data"]
    assert women and all(m["gender"] == "female" for m in women)
    ipl = data(client, "/v1/matches?scope=ipl")["data"]
    assert [m["competition_slug"] for m in ipl] == ["ipl"]
    nr = data(client, "/v1/matches?team=india-men&from=2025-01-01&to=2025-12-31")["data"]
    assert [m["result"] for m in nr] == ["no_result"] and nr[0]["margin"] is None
    assert client.get("/v1/matches?team=nowhere-men").status_code == 404


def test_team_results_carry_scores(client):
    r = data(client, "/v1/teams/india-men/results?scope=ODI&limit=1")["data"][0]
    assert r["scores"] and {s["team"] for s in r["scores"]} <= {"india-men", "australia-men"}


def test_leaderboards(client):
    bat = data(client, "/v1/leaderboards/batting?scope=ODI&gender=male&limit=3")["data"]
    assert [r["runs"] for r in bat] == sorted((r["runs"] for r in bat), reverse=True)
    assert bat[0]["team"] in ("India", "Australia") and "average" in bat[0]
    bowl = data(client, "/v1/leaderboards/bowling?gender=female")["data"]
    assert bowl and "economy" in bowl[0]
    assert client.get("/v1/leaderboards/batting?metric=average").status_code == 400
    assert client.get("/v1/leaderboards/fielding").status_code == 404
