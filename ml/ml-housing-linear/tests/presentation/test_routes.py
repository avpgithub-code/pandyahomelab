import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from fastapi.testclient import TestClient
from presentation_logic.api.main import create_app

client = TestClient(create_app())

VALID_FEATURES = [8.3252, 41.0, 6.984, 1.024, 322.0, 2.556, 37.88, -122.23]


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data


def test_predict_returns_200():
    response = client.post("/predict", json={"data": VALID_FEATURES})
    assert response.status_code == 200


def test_predict_invalid_features_returns_422():
    response = client.post("/predict", json={"data": [1.0, 2.0, 3.0]})
    assert response.status_code == 422


def test_predict_returns_positive_value():
    response = client.post("/predict", json={"data": VALID_FEATURES})
    assert response.status_code == 200
    data = response.json()
    assert data["prediction"] > 0
    assert data["prediction_usd"].startswith("$")
