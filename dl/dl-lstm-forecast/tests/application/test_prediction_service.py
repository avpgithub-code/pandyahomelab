"""Tests for PredictionService — end-to-end orchestration.

Uses a synthetic CSV fixture (~150 days) and 2-epoch training to keep the
suite well under 30s. MLflow is implicitly tested by NOT being reachable
— the service should degrade gracefully (logs warning, skips, never
breaks forecast/predict).
"""
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from application_logic.services.prediction_service import PredictionService
from db_logic.loaders.loaders import BikeShareLoader


@pytest.fixture
def synthetic_loader(tmp_path: Path) -> BikeShareLoader:
    """160-day CSV (just enough for window=14 + val_days=20 + test_days=20)."""
    n = 160
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    trips = 10_000 + 1500 * np.sin(2 * np.pi * np.arange(n) / 7) + 30 * np.arange(n)
    df = pd.DataFrame({"date": dates, "trips": trips.astype(int)})
    path = tmp_path / "synth_bike.csv"
    df.to_csv(path, index=False)
    return BikeShareLoader(data_path=str(path))


@pytest.fixture
def trained_service(synthetic_loader) -> PredictionService:
    """A PredictionService trained for 2 epochs on the synthetic fixture."""
    svc = PredictionService(
        loader=synthetic_loader,
        window_size=14,
        val_days=20,
        test_days=20,
        mc_samples=5,
        forecast_horizon=5,
    )
    svc.train(epochs=2, patience=99, batch_size=16)
    return svc


# ---- train ----

def test_train_marks_service_ready(synthetic_loader):
    svc = PredictionService(
        loader=synthetic_loader, window_size=14, val_days=20, test_days=20,
        mc_samples=5, forecast_horizon=5,
    )
    assert not svc.is_ready
    metrics = svc.train(epochs=2, patience=99, batch_size=16)
    assert svc.is_ready
    assert {"test_rmse", "test_mape", "n_test", "best_val_loss", "epochs_run"} <= set(metrics)


def test_train_is_idempotent_under_lock(synthetic_loader):
    """Concurrent train calls must not re-train — second caller picks up
    cached metrics. This is the [[phase_2a_complete]] thread-safety pattern."""
    svc = PredictionService(
        loader=synthetic_loader, window_size=14, val_days=20, test_days=20,
        mc_samples=5, forecast_horizon=5,
    )
    results = []
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        results.append(svc.train(epochs=2, patience=99, batch_size=16))

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start(); t2.start()
    t1.join(); t2.join()
    assert len(results) == 2
    # Both callers must see the SAME metrics dict (same training run).
    assert results[0] == results[1]


# ---- forecast ----

def test_forecast_shape_with_actuals_overlay(trained_service):
    """Anchor in the middle of the series — all 5 forecast days have
    actuals available, so each point has a non-None actual."""
    result = trained_service.forecast(anchor_date="2024-04-01", horizon=5, n_samples=5)
    assert result["horizon"] == 5
    assert result["window_size"] == 14
    assert result["anchor_date"] == "2024-04-01"
    assert len(result["points"]) == 5
    for i, p in enumerate(result["points"]):
        assert p["day_offset"] == i + 1
        assert p["actual"] is not None
        assert p["lower"] <= p["mean"] <= p["upper"]


def test_forecast_anchor_near_end_has_partial_actuals(trained_service):
    """Anchor = last day of historical series → forecasts extend past it
    → all `actual` values are None."""
    result = trained_service.forecast(anchor_date="2024-06-08", horizon=5, n_samples=5)
    # 2024-01-01 + 159 days = 2024-06-08 (last available date in fixture).
    assert result["anchor_date"] == "2024-06-08"
    actuals = [p["actual"] for p in result["points"]]
    assert all(a is None for a in actuals)


def test_forecast_anchor_outside_range_raises(trained_service):
    with pytest.raises(ValueError, match="outside loaded range"):
        trained_service.forecast(anchor_date="2030-01-01", horizon=5, n_samples=5)


def test_forecast_default_horizon_from_construct(synthetic_loader):
    svc = PredictionService(
        loader=synthetic_loader, window_size=14, val_days=20, test_days=20,
        mc_samples=5, forecast_horizon=7,
    )
    svc.train(epochs=1, patience=99, batch_size=16)
    result = svc.forecast(anchor_date="2024-04-01")  # no explicit horizon/n_samples
    assert result["horizon"] == 7
    assert len(result["points"]) == 7


# ---- get_history ----

def test_get_history_returns_full_series(trained_service):
    hist = trained_service.get_history()
    assert {"dates", "trips", "min_anchor", "max_anchor"} == set(hist)
    assert len(hist["dates"]) == len(hist["trips"]) == 160
    assert hist["dates"][0] == "2024-01-01"
    assert hist["dates"][-1] == "2024-06-08"
    # min_anchor sits one window-length in (window=14 → index 13 → 2024-01-14)
    assert hist["min_anchor"] == "2024-01-14"
    assert hist["max_anchor"] == "2024-06-08"


# ---- get_model_info ----

def test_get_model_info_placeholder_when_untrained(synthetic_loader):
    """Cloudflare-safe path: untrained service must NEVER trigger training
    from /model-info (would 524 on the public route)."""
    svc = PredictionService(
        loader=synthetic_loader, window_size=14, val_days=20, test_days=20,
        mc_samples=5, forecast_horizon=5,
    )
    info = svc.get_model_info()
    assert info["model_type"] == "LSTMForecaster"
    assert info["metrics"] == {}
    assert info["run_id"] is None
    assert info["mlflow_url"] is None
    assert info["split"] is None
    # Verify training was NOT triggered (no race here, just an invariant check).
    assert not svc.is_ready


def test_get_model_info_trained_returns_metrics(trained_service):
    info = trained_service.get_model_info()
    assert info["metrics"]
    assert "test_mape" in info["metrics_display"]
    assert info["split"]["train_samples"] > 0
    # mlflow_url is None because dl-mlflow:5000 is unreachable in test env;
    # that's graceful degradation, not a bug.
    assert info["mlflow_url"] is None
