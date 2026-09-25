"""Tests for presentation layer — HTTP routes."""
import pytest
from fastapi.testclient import TestClient

import presentation_logic.api.routes as routes_mod
from application_logic.services.prediction_service import PredictionService
from presentation_logic.api.main import app


@pytest.fixture(scope="module", autouse=True)
def trained_service():
    """Swap in a pre-trained service so no test waits on warm-up."""
    service = PredictionService()
    service.train()
    original = routes_mod._service
    routes_mod._service = service
    yield
    routes_mod._service = original


client = TestClient(app)


class TestHealth:
    def test_returns_200(self):
        assert client.get("/health").status_code == 200

    def test_required_fields(self):
        data = client.get("/health").json()
        for field in ("status", "timestamp", "version", "request_id"):
            assert field in data


class TestPredict:
    def test_returns_200(self):
        assert client.post("/predict", json={"text": "Great film"}).status_code == 200

    def test_response_shape(self):
        data = client.post("/predict", json={"text": "Great film"}).json()
        for field in ("pipeline", "tokens", "representations", "request_id"):
            assert field in data

    def test_empty_text_returns_422(self):
        assert client.post("/predict", json={"text": ""}).status_code == 422

    def test_missing_text_returns_422(self):
        assert client.post("/predict", json={}).status_code == 422

    def test_too_long_text_returns_422(self):
        assert client.post("/predict", json={"text": "a" * 5001}).status_code == 422


class TestWorkedExample:
    def test_returns_tables(self):
        data = client.get("/worked-example").json()
        assert {"corpus", "one_hot_doc1", "bow", "ngram", "tfidf"} <= set(data)


class TestModelInfo:
    def test_returns_200(self):
        assert client.get("/model-info").status_code == 200

    def test_required_fields(self):
        data = client.get("/model-info").json()
        for field in ("model_type", "architecture", "metrics", "metrics_display",
                      "confusion_matrix", "split", "preprocessing", "comparison", "mlflow_url"):
            assert field in data


class TestDemoUI:
    def test_root_returns_html(self):
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "")

    def test_has_about_trigger_and_feedback_widget(self):
        html = client.get("/").text
        assert 'id="about-trigger"' in html
        assert "/feedback-widget.js" in html

    def test_uses_relative_api_base(self):
        # No hard-coded /ml/... or /dl/... paths copied from another demo.
        html = client.get("/").text
        assert "fetch('/" not in html


class TestAbout:
    def test_returns_200(self):
        assert client.get("/about").status_code == 200
