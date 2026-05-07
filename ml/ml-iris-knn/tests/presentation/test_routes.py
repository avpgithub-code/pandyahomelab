"""Tests for presentation layer — /health and /predict endpoints."""
import pytest
from fastapi.testclient import TestClient

from presentation_logic.api.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_healthy_status(self):
        response = client.get("/health")
        assert response.json()["status"] == "healthy"

    def test_health_has_required_fields(self):
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data


class TestPredictEndpoint:
    SETOSA = {"data": [5.1, 3.5, 1.4, 0.2]}
    VIRGINICA = {"data": [6.5, 3.0, 5.8, 2.2]}

    def test_predict_returns_200(self):
        response = client.post("/predict", json=self.SETOSA)
        assert response.status_code == 200

    def test_predict_returns_required_fields(self):
        response = client.post("/predict", json=self.SETOSA)
        data = response.json()
        assert "prediction" in data
        assert "species" in data
        assert "confidence" in data
        assert "probabilities" in data

    def test_predict_setosa(self):
        response = client.post("/predict", json=self.SETOSA)
        assert response.json()["species"] == "setosa"

    def test_predict_virginica(self):
        response = client.post("/predict", json=self.VIRGINICA)
        assert response.json()["species"] == "virginica"

    def test_predict_invalid_features_returns_422(self):
        response = client.post("/predict", json={"data": [1.0, 2.0]})
        assert response.status_code == 422

    def test_predict_confidence_between_0_and_1(self):
        response = client.post("/predict", json=self.SETOSA)
        confidence = response.json()["confidence"]
        assert 0.0 <= confidence <= 1.0


class TestModelInfoEndpoint:
    def test_model_info_returns_200(self):
        response = client.get("/model-info")
        assert response.status_code == 200

    def test_model_info_has_metrics(self):
        response = client.get("/model-info")
        data = response.json()
        assert "accuracy" in data["metrics"]
        assert "f1_macro" in data["metrics"]

    def test_model_info_accuracy_above_threshold(self):
        response = client.get("/model-info")
        assert response.json()["metrics"]["accuracy"] > 0.9
