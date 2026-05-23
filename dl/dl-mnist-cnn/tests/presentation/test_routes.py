"""Tests for presentation layer — HTTP routes.

The /predict and /model-info handlers go through the module-level
PredictionService singleton in routes.py. Its first invocation triggers
full 60k-sample CNN training, which is ~8 min on NAS CPU — way too slow
for unit tests. The `pretrained_service` autouse fixture monkey-patches
the module's _service with a tiny-subset-trained instance before any
test runs, so /predict returns in <100ms throughout the suite.

Accuracy isn't asserted here — that's an application-logic concern,
already covered in test_classifier.py with the same tiny subset.
"""
import pytest
from fastapi.testclient import TestClient
from torch.utils.data import DataLoader, Subset

import presentation_logic.api.routes as routes_mod
from application_logic.services.prediction_service import PredictionService
from db_logic.loaders.loaders import LocalDataLoader
from db_logic.transforms.preprocessor import N_PIXELS
from presentation_logic.api.main import app


@pytest.fixture(scope="module", autouse=True)
def pretrained_service():
    """Replace routes._service with a tiny-subset-trained instance so /predict
    is fast. Module-scoped — trains once for the whole test file."""
    base = LocalDataLoader()
    train = DataLoader(Subset(base.load_train().dataset, list(range(200))), batch_size=32, shuffle=True)
    test = DataLoader(Subset(base.load_test().dataset, list(range(100))), batch_size=50, shuffle=False)

    service = PredictionService()
    service.train(epochs=1, train_loader=train, test_loader=test)

    original = routes_mod._service
    routes_mod._service = service
    yield
    routes_mod._service = original


client = TestClient(app)
VALID_PIXELS = {"pixels": [0.0] * N_PIXELS}


class TestHealthEndpoint:
    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_healthy_status(self):
        assert client.get("/health").json()["status"] == "healthy"

    def test_health_has_required_fields(self):
        data = client.get("/health").json()
        for field in ("status", "timestamp", "version", "request_id"):
            assert field in data


class TestPredictEndpoint:
    def test_predict_valid_returns_200(self):
        response = client.post("/predict", json=VALID_PIXELS)
        assert response.status_code == 200

    def test_predict_response_shape(self):
        data = client.post("/predict", json=VALID_PIXELS).json()
        for field in ("prediction", "digit", "confidence", "probabilities", "request_id"):
            assert field in data

    def test_predict_returns_valid_digit(self):
        data = client.post("/predict", json=VALID_PIXELS).json()
        assert data["prediction"] in range(10)
        assert data["digit"] == str(data["prediction"])

    def test_predict_confidence_in_unit_interval(self):
        data = client.post("/predict", json=VALID_PIXELS).json()
        assert 0.0 <= data["confidence"] <= 1.0

    def test_predict_probabilities_cover_all_digits(self):
        probs = client.post("/predict", json=VALID_PIXELS).json()["probabilities"]
        assert set(probs.keys()) == {str(i) for i in range(10)}

    def test_predict_wrong_pixel_count_returns_422(self):
        response = client.post("/predict", json={"pixels": [0.0] * 100})
        assert response.status_code == 422

    def test_predict_empty_pixels_returns_422(self):
        response = client.post("/predict", json={"pixels": []})
        assert response.status_code == 422

    def test_predict_pixel_out_of_range_returns_422(self):
        # 0-255 is the allowed range; -1 and 256 should both be rejected.
        response = client.post("/predict", json={"pixels": [-1.0] + [0.0] * (N_PIXELS - 1)})
        assert response.status_code == 422
        response = client.post("/predict", json={"pixels": [256.0] + [0.0] * (N_PIXELS - 1)})
        assert response.status_code == 422

    def test_predict_missing_pixels_field_returns_422(self):
        response = client.post("/predict", json={})
        assert response.status_code == 422


class TestModelInfoEndpoint:
    def test_model_info_returns_200(self):
        assert client.get("/model-info").status_code == 200

    def test_model_info_has_required_fields(self):
        data = client.get("/model-info").json()
        for field in ("model_type", "architecture", "dataset", "classes", "parameters", "metrics"):
            assert field in data

    def test_model_info_dataset_is_mnist(self):
        assert client.get("/model-info").json()["dataset"] == "MNIST"

    def test_model_info_classes_are_0_to_9(self):
        classes = client.get("/model-info").json()["classes"]
        assert classes == [str(i) for i in range(10)]

    def test_model_info_metrics_have_accuracy(self):
        metrics = client.get("/model-info").json()["metrics"]
        assert "accuracy" in metrics
        assert 0.0 <= metrics["accuracy"] <= 1.0


class TestDemoUIEndpoint:
    def test_root_returns_200(self):
        assert client.get("/").status_code == 200

    def test_root_returns_html(self):
        response = client.get("/")
        assert "text/html" in response.headers.get("content-type", "")
        assert "<canvas" in response.text
        assert "dl-mnist-cnn" in response.text


class TestAboutEndpoint:
    def test_about_returns_200(self):
        assert client.get("/about").status_code == 200

    def test_about_has_sections(self):
        data = client.get("/about").json()
        assert "sections" in data
        assert isinstance(data["sections"], list)
        assert len(data["sections"]) > 0
        section_ids = {s.get("id") for s in data["sections"]}
        assert "metrics" in section_ids
        assert "architecture" in section_ids
