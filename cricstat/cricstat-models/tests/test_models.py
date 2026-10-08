"""P1.2: Elo maths, quality measures, the win-rate baseline (no leakage) and the backtest flow."""
import math
import random

import pytest

from application_logic.models import baselines, elo, metrics
from application_logic.services import backtest_service
from db_logic.tracking.mlflow_rest import MlflowClient


def _row(i, date, t1, t2, result="win", winner=None, home=None, runs=None, wkts=None):
    return {"match_key": str(i), "start_date": date, "team1": t1, "team2": t2, "home": home,
            "result": result, "winner": winner if result == "win" else None, "has_play": 1,
            "source": "cricsheet", "margin_runs": runs, "margin_wickets": wkts}


FM = {"India": "1926-05-31", "Australia": "1909-06-15", "Ireland": "2017-06-22"}


def test_expected_score_and_zero_sum_update():
    c = elo.compile_matches([_row(1, "2010-01-01", "India", "Australia", winner="India")], FM)
    preds, ratings, _ = elo.run(c, elo.EloParams(k=20, home=0))
    assert preds == [(0, 0.5)]
    assert ratings == [1510.0, 1490.0]                       # K * (1 - 0.5) each way
    assert sum(ratings) == 3000.0


def test_home_advantage_tie_and_no_result():
    rows = [_row(1, "2010-01-01", "India", "Australia", home="India", winner="India"),
            _row(2, "2010-01-02", "India", "Australia", result="tie"),
            _row(3, "2010-01-03", "India", "Australia", result="no_result")]
    c = elo.compile_matches(rows, FM)
    preds, ratings, _ = elo.run(c, elo.EloParams(k=20, home=100))
    assert preds[0][1] == pytest.approx(1 / (1 + 10 ** (-100 / 400)))
    assert len(preds) == 2                                   # no result: not scored, no update
    e = preds[1][1]
    assert ratings[0] == pytest.approx(1500 + 20 * (1 - preds[0][1]) + 20 * (0.5 - e))


def test_associates_start_lower_and_promotion_changes_regression_target():
    rows = [_row(1, "2010-01-01", "Ireland", "India", winner="India"),
            _row(2, "2019-01-01", "Ireland", "India", winner="Ireland")]
    c = elo.compile_matches(rows, FM)
    assert c.associate_at_start == [True, False]             # Ireland: associate in 2010
    _, r_no, _ = elo.run(c, elo.EloParams(k=0, home=0, delta=300, regress=0.0))
    assert r_no[0] == 1200.0
    _, r_reg, _ = elo.run(c, elo.EloParams(k=0, home=0, delta=300, regress=0.5))
    assert r_reg[0] == 1350.0      # 2019: a Full Member, pulled halfway toward 1500, not 1200


def test_margin_multiplier_is_one_at_a_median_margin_and_until_stops():
    rows = [_row(1, "2010-01-01", "India", "Australia", winner="India", runs=75),
            _row(2, "2011-01-01", "India", "Australia", winner="Australia", wkts=5)]
    c = elo.compile_matches(rows, FM)
    _, plain, _ = elo.run(c, elo.EloParams(k=20, home=0), until="2011-01-01")
    _, marg, _ = elo.run(c, elo.EloParams(k=20, home=0, margin=True), until="2011-01-01")
    assert plain == marg                                     # u = 0.5 and dR = 0 → m = 1
    assert len(elo.run(c, elo.EloParams(), until="2011-01-01")[0]) == 1


def test_metrics_known_values():
    assert metrics.brier([0.5, 1.0], [1, 1]) == 0.125
    assert metrics.log_loss([0.5], [1]) == pytest.approx(math.log(2))
    assert metrics.accuracy([0.7, 0.4, 0.5], [1, 1, 0]) == 0.5
    rel = metrics.reliability([0.55, 0.45, 0.95], [1, 1, 1])
    assert [(b["bin"], b["n"]) for b in rel] == [("0.5-0.6", 2), ("0.9-1.0", 1)]
    assert rel[0]["observed"] == 0.5                         # 0.45 → favourite was team2, lost


def test_calibration_recovers_slope_one_on_calibrated_data():
    rng = random.Random(7)
    p = [rng.uniform(0.05, 0.95) for _ in range(4000)]
    y = [1.0 if rng.random() < q else 0.0 for q in p]
    a, b = metrics.calibration(p, y)
    assert abs(a) < 0.1 and abs(b - 1) < 0.1
    # Twice as extreme as the truth (logits doubled) = overconfident: slope about 0.5.
    over = [1 / (1 + math.exp(-2 * math.log(q / (1 - q)))) for q in p]
    a, b = metrics.calibration(over, y)
    assert b == pytest.approx(0.5, abs=0.06)


def test_win_rate_features_only_use_earlier_matches():
    rows = [_row(i, "2010-01-%02d" % i, "India", "Australia", winner="India") for i in range(1, 6)]
    c = elo.compile_matches(rows, FM)
    feats = baselines.win_rate_features(c)
    assert feats[0][0] == 0.0                                # no history yet
    before = feats[3][0]
    rows[3]["winner"] = "Australia"                          # change match 4's own result
    assert baselines.win_rate_features(elo.compile_matches(rows, FM))[3][0] == before


def _synthetic(seed=3):
    """Six teams with fixed strengths, 2003-2021: Elo must find signal, coin must lose."""
    rng = random.Random(seed)
    strength = {"India": 200, "Australia": 150, "England": 100, "Pakistan": 50,
                "Ireland": -150, "Scotland": -200}
    teams = list(strength)
    rows, i = [], 0
    for year in range(2003, 2022):
        for d in range(1, 61):
            a, b = rng.sample(teams, 2)
            pa = 1 / (1 + 10 ** (-(strength[a] - strength[b]) / 400))
            i += 1
            rows.append(_row(i, "%d-%02d-%02d" % (year, 1 + d // 6, 1 + d % 28), a, b,
                             winner=a if rng.random() < pa else b, runs=40))
    rows.sort(key=lambda r: r["start_date"])
    return rows


def test_backtest_walk_forward_without_leakage(cfg, monkeypatch, tmp_path):
    rows = _synthetic()
    monkeypatch.setattr(backtest_service.data_service, "load_matches",
                        lambda _cfg: (rows, {"data_as_of": "2021-12-31", "build_id": 1,
                                             "by_source": {"cricsheet": len(rows)}}))
    monkeypatch.setattr(backtest_service, "GRID", {"k": (10, 30), "home": (0,), "margin": (False,),
                                                   "regress": (0.0,), "delta": (0, 300)})
    monkeypatch.setattr(backtest_service, "full_members", lambda _p: FM)
    rep = backtest_service.run(cfg, log_to_mlflow=False, out_root=str(tmp_path))
    t = rep["test_a"]
    assert t["elo"]["log_loss"] < t["baselines"]["coin"]["log_loss"]
    assert set(t["params_by_year"]) == {"2019", "2020", "2021"}
    # Leakage check: flipping every 2021 result must not change the parameters chosen for 2021.
    flipped = [dict(r, winner=r["team2"] if r["winner"] == r["team1"] else r["team1"])
               if r["start_date"] >= "2021" else r for r in rows]
    monkeypatch.setattr(backtest_service.data_service, "load_matches",
                        lambda _cfg: (flipped, {"data_as_of": "2021-12-31", "build_id": 1,
                                                "by_source": {"cricsheet": len(rows)}}))
    rep2 = backtest_service.run(cfg, log_to_mlflow=False, out_root=str(tmp_path / "b"))
    assert rep2["test_a"]["params_by_year"]["2021"] == t["params_by_year"]["2021"]
    for name in ("grid.csv", "test_a_predictions.csv", "reliability.csv", "reliability.svg",
                 "ratings_current.csv"):
        assert (tmp_path / rep["report_dir"].split("/")[-1] / name).exists()


def test_mlflow_client_batches_and_drops_nan(monkeypatch):
    calls = []
    client = MlflowClient("http://mlflow.test")
    monkeypatch.setattr(client, "_call", lambda method, path, body=None, query=None:
                        calls.append((path, body)) or {})
    client.log_batch("r1", {"p%d" % i: i for i in range(150)}, {"a": 1.0, "b": float("nan")})
    assert [len(b["params"]) for _, b in calls] == [100, 50]
    assert calls[0][1]["metrics"] == [{"key": "a", "value": 1.0, "timestamp":
                                       calls[0][1]["metrics"][0]["timestamp"], "step": 0}]
