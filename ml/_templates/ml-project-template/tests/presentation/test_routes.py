"""Tests for presentation layer (API routes)."""
from fastapi.testclient import TestClient
from ...presentation_logic.api.main import create_app

client = TestClient(create_app())


def test_health_check():
    """Test /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data
