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


class TestQueries:
    def test_neighbors(self):
        r = client.post("/neighbors", json={"word": "king", "topn": 3})
        assert r.status_code == 200 and "cbow" in r.json()

    def test_analogy(self):
        r = client.post("/analogy", json={"a": "king", "b": "man", "c": "woman"})
        assert r.status_code == 200 and "answers" in r.json()["skipgram"]

    def test_similarity(self):
        assert client.post("/similarity", json={"w1": "king", "w2": "queen"}).status_code == 200

    def test_map(self):
        r = client.post("/map", json={"words": ["king", "queen", "man"]})
        assert r.status_code == 200 and r.json()["cbow"]["points"]

    def test_rejects_non_words(self):
        assert client.post("/neighbors", json={"word": "<script>"}).status_code == 422
        assert client.post("/neighbors", json={"word": ""}).status_code == 422

    def test_map_needs_two_words(self):
        assert client.post("/map", json={"words": ["king"]}).status_code == 422


class TestModelInfo:
    def test_returns_200(self):
        assert client.get("/model-info").status_code == 200

    def test_required_fields(self):
        data = client.get("/model-info").json()
        for field in ("model_type", "architecture", "metrics", "metrics_display",
                      "comparison", "split", "preprocessing", "mlflow_url"):
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
