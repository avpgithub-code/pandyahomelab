"""P1.4: forecast.sqlite writer, promotion rule, result overlay and the daily forecast end to end."""
import os
import sqlite3

import pytest

from application_logic.services import forecast_service as fs
from db_logic.repository import forecast_store, supplement_store, tournament_store
from shared.exceptions import DataCheckError
from tests.conftest import ROOT, make_serving_db

CHAMPION = {"model_version": "elo-v1", "registered_version": "1", "mlflow_run_id": "r1",
            "elo": {"k": 20, "home": 75, "margin": True, "regress": 0.05, "delta": 400},
            "sigma_a": 3.36, "n_simulations": 200, "seed": 1, "trained_at": "2026-10-08",
            "conditions": {"by_country": {"South Africa": 0.076}, "global": 0.065, "tie": 0.011},
            "metrics": {"test_a.log_loss": 0.605, "test_b.log_loss": 0.548},
            "gates": {"test_a_passes": True, "gate3_test_b_not_worse": True,
                      "gate4_replay_and_sums": True},
            "reliability_test_a": [{"bin": "0.5-0.6", "n": 3, "predicted": 0.55, "observed": 0.6}]}


def test_team_uid():
    assert forecast_store.team_uid("United States of America") == "united-states-of-america-men"
    assert forecast_store.team_uid("India", "female") == "india-women"


def test_writer_swaps_atomically_and_keeps_the_live_file_on_failure(tmp_path):
    path = str(tmp_path / "forecast.sqlite")
    with forecast_store.ForecastWriter(path) as w:
        uids = w.teams(["India", "Afghanistan"], ["India"])
        w.model_version("elo-v1", {"x": 1}, "1", "r1", "now")
        fid = w.forecast({"tournament": "t", "created_at": "now", "data_as_of": "d", "build_id": 1,
                          "fingerprint": "f1", "n_simulations": 10, "model_version": "elo-v1",
                          "mlflow_run_id": None, "days_to_start": 1, "sigma": 1.0, "notes": ""},
                         {uids["India"]: {"champion": 0.7}, uids["Afghanistan"]: {"champion": 0.3}},
                         [])
        assert w.check(fid, {"champion": 1}) == []
        w.commit()
    assert not os.path.exists(path + ".new")
    assert forecast_store.last_forecast(path, "t")["fingerprint"] == "f1"
    with pytest.raises(RuntimeError):
        with forecast_store.ForecastWriter(path) as w:
            w.teams(["India"], ["India"])
            fid = w.forecast({"tournament": "t", "created_at": "now", "data_as_of": "d",
                              "build_id": 1, "fingerprint": "f2", "n_simulations": 10,
                              "model_version": "elo-v1", "mlflow_run_id": None,
                              "days_to_start": 1, "sigma": 1.0, "notes": ""},
                             {"india-men": {"champion": 0.5}}, [])
            assert w.check(fid, {"champion": 1}) == ["stage champion sums to 0.500000, expected 1"]
            raise RuntimeError("checks failed")
    assert forecast_store.last_forecast(path, "t")["fingerprint"] == "f1"     # untouched
    assert not os.path.exists(path + ".new")
    c = sqlite3.connect(path)
    assert c.execute("SELECT in_serving FROM team_identities WHERE team_uid = 'afghanistan-men'"
                     ).fetchone() == (0,)


def test_promotion_rule():
    cand = dict(CHAMPION)
    assert fs.promotion_decision(cand, None, owner_approved=False)["promote"] is False
    assert fs.promotion_decision(cand, None, owner_approved=True)["promote"] is True
    worse = dict(cand, metrics={"test_a.log_loss": 0.610, "test_b.log_loss": 0.548})
    d = fs.promotion_decision(worse, CHAMPION, owner_approved=False)
    assert d["promote"] is False and "test_a.log_loss regressed" in d["reasons"][0]
    tiny = dict(cand, metrics={"test_a.log_loss": 0.6065, "test_b.log_loss": 0.552})
    assert fs.promotion_decision(tiny, CHAMPION, False)["promote"] is True      # within tolerance
    failed = dict(cand, gates=dict(cand["gates"], gate3_test_b_not_worse=False))
    assert fs.promotion_decision(failed, CHAMPION, True)["promote"] is False


def test_overlay_fills_played_fixtures_by_scorecard_id():
    fixtures = [{"match_key": "1556789", "result": ""}, {"match_key": "1556790", "result": ""}]
    rows = [{"match_key": "1556789", "team1": "Australia", "team2": "India", "result": "win",
             "winner": "India", "has_play": 1}]
    assert fs.overlay_results(fixtures, rows) == 1
    assert fixtures[0]["winner"] == "India" and fixtures[1]["result"] == ""


WC27 = tournament_store.read_format(os.path.join(ROOT, "tournaments"), "wc2027")
FIELD = tournament_store.read_format(os.path.join(ROOT, "tournaments"),
                                     "wcq2027")["simulation_field"]


def _db(cfg):
    teams = sorted(set(WC27["teams"]) - {"Afghanistan"}) + FIELD
    matches = [("%d" % (100 + i), "2026-0%d-1%d" % (1 + i % 9, i % 10), a, b, "India", "win", a)
               for i, (a, b) in enumerate(zip(teams, teams[1:] + teams[:1]))]
    make_serving_db(cfg.SERVING_DB, matches)
    supplement_store.write_results(cfg.SUPPLEMENT_DIR, [])
    supplement_store.write_totals(cfg.SUPPLEMENT_DIR, [])


def test_daily_forecast_writes_skips_and_forces(cfg, monkeypatch, tmp_path):
    monkeypatch.setenv("CRICSTAT_FORECAST_DB", str(tmp_path / "forecast.sqlite"))
    monkeypatch.setenv("CRICSTAT_FULL_MEMBERS", os.path.join(ROOT, "ratings", "icc_full_members.csv"))
    from shared.config import get_config
    cfg = get_config(reload=True)
    _db(cfg)
    monkeypatch.setattr(fs, "load_champion", lambda _cfg, client=None: dict(CHAMPION))
    monkeypatch.setattr(fs, "_log_forecast", lambda *a, **k: None)
    first = fs.forecast(cfg)
    assert first["result"] == "written" and first["n_simulations"] == 200
    assert fs.forecast(cfg)["result"] == "unchanged"
    again = fs.forecast(cfg, force=True)
    assert again["result"] == "written" and again["forecast_id"] == first["forecast_id"] + 1
    c = sqlite3.connect(cfg.FORECAST_DB)
    sums = dict(c.execute("SELECT stage, ROUND(SUM(probability), 6) FROM forecast_team"
                          " WHERE forecast_id = ? GROUP BY stage", (again["forecast_id"],)))
    assert sums == {"champion": 1.0, "final": 2.0, "group": 12.0, "qualified": 4.0, "semi": 4.0,
                    "super7": 7.0, "super_series": 3.0}
    assert c.execute("SELECT COUNT(*) FROM team_ratings").fetchone()[0] > 0
    assert c.execute("SELECT COUNT(*) FROM backtest_metrics").fetchone()[0] == 2


def test_forecast_refuses_bad_sums(cfg, monkeypatch, tmp_path):
    monkeypatch.setenv("CRICSTAT_FORECAST_DB", str(tmp_path / "forecast.sqlite"))
    monkeypatch.setenv("CRICSTAT_FULL_MEMBERS", os.path.join(ROOT, "ratings", "icc_full_members.csv"))
    from shared.config import get_config
    cfg = get_config(reload=True)
    _db(cfg)
    monkeypatch.setattr(fs, "load_champion", lambda _cfg, client=None: dict(CHAMPION))
    monkeypatch.setattr(fs, "_log_forecast", lambda *a, **k: None)
    monkeypatch.setattr(fs, "EXPECT", dict(fs.EXPECT, champion=2))
    with pytest.raises(DataCheckError, match="live forecast kept"):
        fs.forecast(cfg)
    assert not os.path.exists(cfg.FORECAST_DB)
