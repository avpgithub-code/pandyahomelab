"""Teams, meta and status endpoints; and the reopen-on-swap behaviour (F3 §8)."""
from tests.conftest import fixture_matches, ingest, match, pipeline, squad


def data(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_team_list_and_identity(client):
    women = data(client, "/v1/teams?gender=female")
    assert {t["slug"] for t in women} == {"india-women", "england-women"}
    t = data(client, "/v1/teams/india-men")
    assert t["name"] == "India" and t["gender_label"] == "men"
    assert {f["format"] for f in t["formats"]} == {"ODI", "T20I", "TEST"}


def test_record_and_win_pct(client):
    rows = {r["format"]: r for r in data(client, "/v1/teams/india-men/record")}
    odi = rows["ODI"]
    assert (odi["matches"], odi["won"], odi["lost"], odi["no_result"]) == (3, 1, 1, 1)
    assert odi["win_pct"] == 50.0                       # no result leaves the denominator
    scoped = data(client, "/v1/teams/india-men/record?scope=ODI")[0]
    assert scoped["win_pct"] == 50.0 and scoped["matches"] == 3


def test_record_in_a_date_window(client):
    all_odi = data(client, "/v1/teams/india-men/record?scope=ODI")[0]
    y2024 = data(client, "/v1/teams/india-men/record?scope=ODI&from=2024&to=2024")[0]
    assert (all_odi["matches"], y2024["matches"]) == (3, 2) and y2024["win_pct"] == 50.0
    assert data(client, "/v1/teams/india-men/record?scope=ODI&from=2030") == []
    assert client.get("/v1/teams/india-men/record?from=2024").status_code == 400


def test_all_team_records_in_one_call(client):
    rows = {r["slug"]: r for r in data(client, "/v1/records/teams?scope=ODI")}
    one = data(client, "/v1/teams/india-men/record?scope=ODI")[0]
    india = rows["india-men"]
    assert (india["matches"], india["won"], india["win_pct"]) == (one["matches"], one["won"],
                                                                  one["win_pct"])
    assert india["format"] == "ODI" and india["last_date"]
    y2024 = {r["slug"]: r for r in data(client, "/v1/records/teams?scope=ODI&from=2024&to=2024")}
    assert y2024["india-men"]["matches"] == 2
    url = "/v1/records/teams?scope=%s&gender=%s"
    women = [r for f in ("ODI", "T20I", "TEST") for r in data(client, url % (f, "female"))]
    assert women and all(r["gender"] == "female" for r in women)
    assert all(r["gender"] == "male" for r in data(client, url % ("ODI", "male")))
    assert client.get("/v1/records/teams").status_code == 400          # scope is required


def test_results_head_to_head_home_away_years(client):
    res = data(client, "/v1/teams/india-men/results?scope=ODI")
    assert [r["match_id"] for r in res] == ["9007", "9002", "9001"]
    assert res[0]["outcome"] == "no_result" and res[2]["home_away"] == "home"
    h2h = data(client, "/v1/teams/india-men/head-to-head?scope=ODI&opponent=australia-men")
    assert h2h[0]["opponent"]["slug"] == "australia-men" and h2h[0]["last_outcome"] == "no_result"
    ha = {r["where_played"]: r for r in data(client, "/v1/teams/india-men/home-away?scope=ODI")}
    assert ha["home"]["matches"] == 2 and ha["away"]["matches"] == 1
    assert client.get("/v1/teams/mumbai-indians-men/home-away").status_code == 400
    years = data(client, "/v1/teams/india-men/years")
    assert [y["year"] for y in years] == [2024, 2025]


def test_top_players_counts_only_this_team(client):
    runs = data(client, "/v1/teams/india-men/top-players?metric=runs&limit=3")
    assert len(runs) >= 2 and [r["runs"] for r in runs] == sorted((r["runs"] for r in runs),
                                                                  reverse=True)
    kohli_india = next(r for r in data(client, "/v1/teams/india-men/top-players?limit=20")
                       if r["name"] == "V Kohli")
    kohli_mi = next(r for r in data(client, "/v1/teams/mumbai-indians-men/top-players?limit=20")
                    if r["name"] == "V Kohli")
    assert kohli_india["matches"] == 5 and kohli_mi["matches"] == 1
    wk = data(client, "/v1/teams/australia-men/top-players?metric=wickets&scope=ODI")
    assert wk and "economy" in wk[0]


def test_meta(client):
    scopes = {s["scope"]: s for s in data(client, "/v1/meta/scopes")}
    assert scopes["TEST"]["in_v1_tabs"] and scopes["ipl"]["kind"] == "league"
    comps = data(client, "/v1/meta/competitions?featured=true")
    assert [c["competition_slug"] for c in comps] == ["ipl"] and comps[0]["seasons"] == ["2024"]
    metrics = data(client, "/v1/meta/metrics")
    assert any(m["object"] == "v_player_bowling" and m["column"] == "economy" for m in metrics)


def test_status(client):
    s = data(client, "/v1/status")
    assert s["build"]["build_id"] == 1 and s["counts"]["matches"] == 7
    assert s["ingest_runs"][0]["mode"] == "full" and s["ingest_runs"][0]["status"] == "success"


def test_new_build_is_picked_up_without_restart(client, home):
    """Run last: adds a match, rebuilds (os.replace), and the same client sees build 2."""
    docs = fixture_matches()
    docs["9008"] = match("ODI", "international", "male", "2025-02-10", ("India", "Australia"),
                         {"India": squad("IndM"), "Australia": squad("AusM")},
                         "Wankhede Stadium, Mumbai", "Mumbai", 10, "India")
    ingest(home, {"9008": docs["9008"]}, name="recent.zip", mode="recent")
    s = pipeline(home, "build")
    assert s["status"] == "success" and s["build_id"] == 2
    r = client.get("/v1/teams/india-men/record?scope=ODI")
    assert r.headers["etag"] == '"2"' and r.json()["data"][0]["matches"] == 4


def test_source_freshness():
    from datetime import datetime, timezone

    from application_logic.services.meta_service import source_freshness
    runs = [{"mode": "register", "status": "success", "finished_at": "2026-10-06T14:30:23Z",
             "source_last_modified": None},
            {"mode": "recent", "status": "success", "finished_at": "2026-10-06T10:30:11Z",
             "source_last_modified": "2026-09-17T21:53:14Z"},
            {"mode": "recent", "status": "success", "finished_at": "2026-10-05T10:30:00Z",
             "source_last_modified": "2026-09-17T21:53:14Z"}]
    s = source_freshness(runs, datetime(2026, 10, 6, 22, 0, tzinfo=timezone.utc))
    assert s["last_updated"] == "2026-09-17T21:53:14Z"
    assert s["last_checked"] == "2026-10-06T10:30:11Z"
    assert s["days_since_update"] == 19 and s["stale"]
    fresh = source_freshness(runs, datetime(2026, 9, 20, tzinfo=timezone.utc))
    assert not fresh["stale"]
    unknown = source_freshness([{"mode": "recent", "status": "success", "finished_at": "x",
                                 "source_last_modified": None}])
    assert unknown["last_updated"] is None and not unknown["stale"]
