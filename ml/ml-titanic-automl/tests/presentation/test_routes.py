"""Tests for presentation layer — routes, Pydantic v2 validation."""
import sys
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


VALID_PASSENGER = {
    "pclass": 1, "sex": "female", "age": 28.0,
    "sibsp": 0, "parch": 0, "fare": 100.0, "embarked": "S"
}

MOCK_PREDICT_RESULT = {
    "prediction": 1, "survived": True,
    "survival_label": "Survived", "confidence": 0.87,
}

MOCK_MODEL_INFO = {
    "model_type": "AutoML Classifier",
    "best_model": "LogisticRegression",
    "dataset": "Titanic",
    "n_samples": 891,
    "n_features": 7,
    "algorithms_compared": 5,
    "optimized_for": "AUC",
    "leaderboard": [{"Model": "LR", "Accuracy": 0.82, "AUC": 0.87, "F1": 0.80}],
    "metrics": {"accuracy": 0.82, "auc": 0.87, "f1": 0.80, "precision": 0.81, "recall": 0.79},
    "run_id": "abc123",
    "experiment_id": "1",
    "mlflow_url": "/mlflow/#/experiments/1/runs/abc123",
}


@pytest.fixture(scope="module")
def client():
    mock_svc = MagicMock()
    mock_svc.predict.return_value = MOCK_PREDICT_RESULT
    mock_svc.get_model_info.return_value = MOCK_MODEL_INFO

    with patch("presentation_logic.api.routes._get_service", return_value=mock_svc):
        from presentation_logic.api.main import create_app
        with TestClient(create_app()) as c:
            yield c


def test_health_returns_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_predict_returns_200(client):
    r = client.post("/predict", json=VALID_PASSENGER)
    assert r.status_code == 200


def test_predict_returns_valid_survival(client):
    r = client.post("/predict", json=VALID_PASSENGER)
    data = r.json()
    assert data["prediction"] in (0, 1)
    assert isinstance(data["survived"], bool)
    assert data["survival_label"] in ("Survived", "Did Not Survive")


def test_predict_invalid_pclass_returns_422(client):
    bad = {**VALID_PASSENGER, "pclass": 5}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_predict_invalid_sex_returns_422(client):
    bad = {**VALID_PASSENGER, "sex": "unknown"}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_predict_business_rule_returns_422(client):
    bad = {**VALID_PASSENGER, "pclass": 1, "fare": 0.5}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_model_info_returns_200(client):
    r = client.get("/model-info")
    assert r.status_code == 200


def test_model_info_has_leaderboard(client):
    r = client.get("/model-info")
    data = r.json()
    assert "leaderboard" in data
    assert len(data["leaderboard"]) >= 1
