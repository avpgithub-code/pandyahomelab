"""Predictor endpoints (P1.5) over a small forecast.sqlite written with cricstat-models' own writer
(loaded by file path: both services have packages named db_logic), so the schema can't drift."""
import importlib.util
import json
import os

import pytest

from tests.conftest import CRICSTAT

STORE = CRICSTAT / "cricstat-models" / "db-logic" / "repository" / "forecast_store.py"


def _store():
    spec = importlib.util.spec_from_file_location("models_forecast_store", str(STORE))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PARAMS = {"family": "elo", "elo": {"k": 20, "home": 75, "margin": True, "regress": 0.05,
                                   "delta": 400},
          "sigma_a": 3.36, "trained_at": "2026-10-08", "data_as_of": "2026-10-07",
          "metrics": {"test_a.log_loss": 0.605, "test_b.log_loss": 0.548,
                      "test_a.win_rate.log_loss": 0.662, "test_b.win_rate.log_loss": 0.659},
          "gates": {"test_a_passes": True},
          "backtest": {"test_c": {"wc2019": {"champion": "England"}},
                       "test_a": {"coin": {"accuracy": float("nan")}}}}      # as in the real data


def _run(fs, created, as_of):
    return {"tournament": "wc2027", "created_at": created, "data_as_of": as_of, "build_id": 1,
            "fingerprint": as_of, "n_simulations": 1000, "model_version": "elo-v1",
            "mlflow_run_id": "run1", "days_to_start": 360, "sigma": 34.8, "notes": ""}


@pytest.fixture(scope="module")
def forecast_db(tmp_path_factory):
    fs = _store()
    path = str(tmp_path_factory.mktemp("forecast") / "forecast.sqlite")
    with fs.ForecastWriter(path) as w:
        uid = w.teams(["India", "Australia", "Afghanistan", "Kenya"], ["India", "Australia",
                                                                      "Kenya"])
        w.model_version("elo-v1", PARAMS, "1", "run1", "2026-10-08")
        w.ratings("elo-v1", [(uid["India"], "2026-09-01", "1", 1600.0),
                             (uid["Australia"], "2026-09-01", "1", 1500.0),
                             (uid["India"], "2026-10-05", "2", 1615.0),
                             (uid["Australia"], "2026-10-05", "2", 1485.0),
                             (uid["Afghanistan"], "2026-08-15", "3", 1480.0),
                             (uid["Kenya"], "2013-10-04", "4", 1050.0)])
        probs1 = {uid["India"]: {"semi": 0.6, "champion": 0.5},
                  uid["Australia"]: {"semi": 0.5, "champion": 0.3},
                  uid["Afghanistan"]: {"semi": 0.2, "champion": 0.2}}
        w.forecast(_run(fs, "2026-10-01T05:40:00Z", "2026-10-01"), probs1, [])
        probs2 = {uid["India"]: {"semi": 0.7, "champion": 0.6},
                  uid["Australia"]: {"semi": 0.4, "champion": 0.2},
                  uid["Afghanistan"]: {"semi": 0.2, "champion": 0.2}}
        w.forecast(_run(fs, "2026-10-08T05:40:00Z", "2026-10-07"), probs2,
                   [{"match_id": "2", "start_date": "2026-10-05", "team1_uid": uid["India"],
                     "team2_uid": uid["Australia"], "result": "win", "winner_uid": uid["India"],
                     "source": "cricsheet"}])
        w.backtest("elo-v1", [("summary", "elo", "test_a.log_loss", 0.605)],
                   [("test_a", "elo", "0.5-0.6", 300, 0.55, 0.6)])
        w.meta("tournament:wc2027", json.dumps({
            "id": "wc2027", "name": "ICC Men's Cricket World Cup 2027", "start": "2027-10-02",
            "end": "2027-11-21", "hosts": ["South Africa"], "matches": 57, "played": 0,
            "groups": {"A": ["India", "Australia", "Afghanistan"]}, "assumptions": ["TBC x"]}))
        w.meta("fixtures:wc2027", json.dumps([
            {"match_no": "4", "stage": "group", "slot1": "Australia", "slot2": "India",
             "date": "2027-10-07",
             "chances": {"team1": 0.36, "team2": 0.56, "tie": 0.01, "no_result": 0.07}},
            {"match_no": "55", "stage": "semi", "slot1": "S7-1", "slot2": "S7-4",
             "date": "2027-11-17"}]))
        w.meta("venues:wc2027", json.dumps([{"stadium": "Wanderers Stadium", "city": "Johannesburg",
                                             "capacity": 34000, "history": {"odis": 36}}]))
        w.commit()
    return path


@pytest.fixture(scope="module")
def fclient(home, forecast_db):
    from fastapi.testclient import TestClient

    from presentation_logic.api.app import create_app
    from shared.config import Config

    os.environ["CRICSTAT_HOME"] = str(home)
    os.environ["CRICSTAT_FORECAST_DB"] = forecast_db
    try:
        with TestClient(create_app(Config())) as c:
            yield c
    finally:
        del os.environ["CRICSTAT_FORECAST_DB"]


def test_no_forecast_file_is_a_503_only_for_predictor_endpoints(client):
    r = client.get("/v1/forecasts/wc-2027/latest")
    assert r.status_code == 503 and r.json()["title"] == "Forecast unavailable"
    assert client.get("/v1/teams").status_code == 200


def test_latest(fclient):
    r = fclient.get("/v1/forecasts/wc-2027/latest")
    assert r.status_code == 200
    d = r.json()["data"]
    assert [t["team"] for t in d["teams"]] == ["India", "Australia", "Afghanistan"]
    india = d["teams"][0]
    assert india["probabilities"] == {"semi": 0.7, "champion": 0.6}
    assert (india["slug"], india["rating"], india["group"], india["direct_qualifier"]) == \
        ("india-men", 1615.0, "A", True)
    assert d["teams"][2]["slug"] is None                      # Afghanistan: no team page
    assert d["forecast"]["forecast_id"] == 2 and d["forecast"]["rating_uncertainty_sd"] == 34.8
    assert d["tournament"]["name"].startswith("ICC Men's") and d["assumptions"] == ["TBC x"]
    assert "Afghanistan" in d["disclosures"]["afghanistan"] and d["disclosures"]["not_advice"]
    assert "reviewed results list" in r.json()["meta"]["coverage"]
    etag = r.headers["etag"]
    assert etag.endswith('-f2"')
    assert fclient.get("/v1/forecasts/wc-2027/latest",
                       headers={"if-none-match": etag}).status_code == 304


def test_history_for_a_team_and_for_all(fclient):
    d = fclient.get("/v1/forecasts/wc-2027/history?team=india-men").json()["data"]
    assert [s["probabilities"]["champion"] for s in d["series"]] == [0.5, 0.6]
    assert d["series"][1]["moved_by"][0]["winner"] == "India"
    afg = fclient.get("/v1/forecasts/wc-2027/history?team=afghanistan-men").json()["data"]
    assert afg["series"][1]["moved_by"] == []                  # India v Australia didn't involve it
    allt = fclient.get("/v1/forecasts/wc-2027/history").json()["data"]
    assert allt["series"][0]["probabilities"] == {"india-men": 0.5, "australia-men": 0.3,
                                                  "afghanistan-men": 0.2}
    assert fclient.get("/v1/forecasts/wc-2027/history?team=narnia-men").status_code == 404
    assert fclient.get("/v1/forecasts/wc-2031/latest").status_code == 404


def test_ratings_rank_only_active_teams(fclient):
    rows = fclient.get("/v1/ratings?scope=ODI&gender=male").json()["data"]
    assert [(r["team"], r["rank"], r["matches"]) for r in rows] == [
        ("India", 1, 2), ("Australia", 2, 2), ("Afghanistan", 3, 1), ("Kenya", None, 1)]
    assert fclient.get("/v1/ratings?scope=T20I").status_code == 400
    h = fclient.get("/v1/ratings/india-men/history").json()["data"]
    assert [p["rating"] for p in h["points"]] == [1600.0, 1615.0]
    assert fclient.get("/v1/ratings/narnia-men/history").status_code == 404


def test_backtest_and_admin(fclient):
    d = fclient.get("/v1/models/predictor/backtest").json()["data"]
    assert d["champion"]["model_version"] == "elo-v1" and d["champion"]["elo"]["home"] == 75
    assert [c["status"] for c in d["comparison"]] == ["live", "reference", "planned", "planned"]
    assert d["comparison"][1]["test_b_log_loss"] == 0.659
    assert d["backtest"]["test_c"]["wc2019"]["champion"] == "England"
    assert d["reliability"][0]["bin"] == "0.5-0.6"
    assert d["backtest"]["test_a"]["coin"]["accuracy"] is None   # NaN → null, not a 500
    jobs = fclient.get("/v1/admin/jobs").json()["data"]
    assert jobs["forecast"]["forecast_id"] == 2


def test_fixtures_and_venues(fclient):
    d = fclient.get("/v1/forecasts/wc-2027/fixtures").json()["data"]
    first, semi = d["fixtures"]
    assert (first["slot1_slug"], first["slot2_slug"]) == ("australia-men", "india-men")
    assert first["chances"]["team2"] == 0.56
    assert semi["slot1_slug"] is None and "chances" not in semi
    assert d["venues"][0]["capacity"] == 34000 and "Wikipedia" in d["source"]
    assert fclient.get("/v1/forecasts/wc-2031/fixtures").status_code == 404


def test_last_change_reports_the_most_recent_move():
    from application_logic.services.forecast_service import last_changes
    s = [{"forecast_id": 1, "data_as_of": "2026-10-07", "match_no": "4", "team1": "Australia",
          "team2": "India", "p_team1": 0.36, "p_team2": 0.56},
         {"forecast_id": 2, "data_as_of": "2026-11-02", "match_no": "4", "team1": "Australia",
          "team2": "India", "p_team1": 0.34, "p_team2": 0.58},
         {"forecast_id": 3, "data_as_of": "2026-11-09", "match_no": "4", "team1": "Australia",
          "team2": "India", "p_team1": 0.34, "p_team2": 0.58}]       # neither played: no move
    got = last_changes(s)["4"]
    assert (got["team1_pts"], got["team2_pts"], got["data_as_of"]) == (-2.0, 2.0, "2026-11-02")
    assert last_changes(s[:1]) == {}
