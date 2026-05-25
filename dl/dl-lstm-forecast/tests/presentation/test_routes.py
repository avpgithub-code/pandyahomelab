"""Tests for presentation layer — HTTP routes.

The /forecast and /model-info handlers go through the module-level
PredictionService singleton in routes.py. Its first invocation triggers
LSTM training on the real CitiBike CSV, which is ~10s on NAS CPU — fine
in production but slow for unit tests. The `pretrained_service` autouse
fixture monkey-patches the module's _service with a tiny-synthetic-
trained instance before any test runs, so /forecast returns in <100ms
throughout the suite.

Accuracy isn't asserted here — that's an application-logic concern,
already covered in test_forecaster.py and test_prediction_service.py.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import presentation_logic.api.routes as routes_mod
from application_logic.services.prediction_service import PredictionService
from db_logic.loaders.loaders import BikeShareLoader
from presentation_logic.api.main import app


@pytest.fixture(scope="module", autouse=True)
def pretrained_service(tmp_path_factory):
    """Replace routes._service with a tiny-synthetic-trained instance so
    /forecast is fast. Module-scoped — trains once for the whole file."""
    tmp = tmp_path_factory.mktemp("bike_share_routes")
    n = 160
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    trips = 10_000 + 1500 * np.sin(2 * np.pi * np.arange(n) / 7) + 30 * np.arange(n)
    df = pd.DataFrame({"date": dates, "trips": trips.astype(int)})
    csv_path = tmp / "synth_bike.csv"
    df.to_csv(csv_path, index=False)
    loader = BikeShareLoader(data_path=str(csv_path))
    service = PredictionService(
        loader=loader, window_size=14, val_days=20, test_days=20,
        mc_samples=5, forecast_horizon=5,
    )
    service.train(epochs=2, patience=99, batch_size=16)
    original = routes_mod._service
    routes_mod._service = service
    yield
    routes_mod._service = original


client = TestClient(app)


# ---- /health ----

class TestHealth:
    def test_returns_200(self):
        assert client.get("/health").status_code == 200

    def test_status_healthy(self):
        assert client.get("/health").json()["status"] == "healthy"

    def test_required_fields(self):
        data = client.get("/health").json()
        for field in ("status", "timestamp", "version", "request_id"):
            assert field in data


# ---- /history ----

class TestHistory:
    def test_returns_200(self):
        assert client.get("/history").status_code == 200

    def test_returns_full_series(self):
        data = client.get("/history").json()
        assert len(data["dates"]) == len(data["trips"]) == 160
        assert data["dates"][0] == "2024-01-01"

    def test_anchor_bounds(self):
        data = client.get("/history").json()
        # window_size=14 → first valid anchor is index 13 = 2024-01-14
        assert data["min_anchor"] == "2024-01-14"
        assert data["max_anchor"] == "2024-06-08"


# ---- /forecast ----

VALID_REQ = {"anchor_date": "2024-04-01"}


class TestForecast:
    def test_returns_200(self):
        assert client.post("/forecast", json=VALID_REQ).status_code == 200

    def test_response_shape(self):
        data = client.post("/forecast", json=VALID_REQ).json()
        for field in ("anchor_date", "horizon", "window_size", "points", "request_id"):
            assert field in data
        assert len(data["points"]) == 5  # service's default horizon (fixture)
        for p in data["points"]:
            for field in ("day_offset", "date", "mean", "lower", "upper", "actual"):
                assert field in p

    def test_band_ordering(self):
        data = client.post("/forecast", json=VALID_REQ).json()
        for p in data["points"]:
            assert p["lower"] <= p["mean"] <= p["upper"]

    def test_actuals_overlay_present_for_historical_anchor(self):
        # 2024-04-01 anchor + 5 days = ends 2024-04-06, all within fixture range.
        data = client.post("/forecast", json=VALID_REQ).json()
        actuals = [p["actual"] for p in data["points"]]
        assert all(a is not None for a in actuals)

    def test_actuals_none_for_anchor_at_end(self):
        # 2024-06-08 is the last historical date; all 5 forecast days extend past it.
        data = client.post("/forecast", json={"anchor_date": "2024-06-08"}).json()
        assert all(p["actual"] is None for p in data["points"])

    def test_anchor_outside_range_returns_400(self):
        res = client.post("/forecast", json={"anchor_date": "2030-01-01"})
        assert res.status_code == 400
        assert "outside loaded range" in res.json()["detail"]

    def test_invalid_anchor_format_returns_422(self):
        res = client.post("/forecast", json={"anchor_date": "not-a-date"})
        assert res.status_code == 422

    def test_horizon_out_of_bounds_returns_422(self):
        res = client.post("/forecast", json={"anchor_date": "2024-04-01", "horizon": 99})
        assert res.status_code == 422
        res = client.post("/forecast", json={"anchor_date": "2024-04-01", "horizon": 0})
        assert res.status_code == 422

    def test_n_samples_out_of_bounds_returns_422(self):
        res = client.post("/forecast", json={"anchor_date": "2024-04-01", "n_samples": 999})
        assert res.status_code == 422

    def test_missing_anchor_returns_422(self):
        assert client.post("/forecast", json={}).status_code == 422


# ---- /model-info ----

class TestModelInfo:
    def test_returns_200(self):
        assert client.get("/model-info").status_code == 200

    def test_required_fields(self):
        data = client.get("/model-info").json()
        for field in ("model_type", "architecture", "dataset", "target", "parameters", "metrics"):
            assert field in data

    def test_model_type(self):
        assert client.get("/model-info").json()["model_type"] == "LSTMForecaster"

    def test_metrics_have_test_mape(self):
        m = client.get("/model-info").json()["metrics"]
        assert "test_mape" in m
        assert "test_rmse" in m


# ---- / (demo UI) ----

class TestDemoUI:
    def test_root_returns_200(self):
        assert client.get("/").status_code == 200

    def test_root_returns_html(self):
        res = client.get("/")
        assert "text/html" in res.headers.get("content-type", "")
        assert "<canvas" in res.text
        assert "dl-lstm-forecast" in res.text
        # Smoke-test that the feedback widget embed is present per
        # [[feedback_widget_v1]] — one-line script tag before </body>.
        assert '/feedback-widget.js' in res.text


# ---- /about ----

class TestAbout:
    def test_returns_200(self):
        assert client.get("/about").status_code == 200

    def test_has_required_sections(self):
        data = client.get("/about").json()
        ids = {s.get("id") for s in data["sections"]}
        # Sections the UI's substituteTokens() expects to find.
        for section in ("metrics", "architecture", "dataset"):
            assert section in ids, f"missing section: {section}"
