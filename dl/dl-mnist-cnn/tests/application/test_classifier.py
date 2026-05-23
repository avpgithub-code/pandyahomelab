"""Tests for application-logic — MnistCNN, DigitClassifier, PredictionService.

Uses a tiny MNIST subset (200 train / 100 test, 1 epoch) for the training
fixture so the whole suite stays under ~30s on NAS CPU. Accuracy is NOT
asserted here — the production target (>=98% on full 60k/3-epoch) gets its
own opt-in slow test that we run at integration time, not on every iteration.
"""
import pytest
import torch
from torch.utils.data import DataLoader, Subset

from db_logic.loaders.loaders import LocalDataLoader
from db_logic.transforms.preprocessor import DataPreprocessor, N_PIXELS
from application_logic.model.classifier import (
    ARCHITECTURE,
    DEFAULT_EPOCHS,
    DigitClassifier,
    LEARNING_RATE,
    MnistCNN,
)
from application_logic.services.prediction_service import PredictionService


# ---------- shared tiny loaders (module-scoped — train once) ---------------------

@pytest.fixture(scope="module")
def tiny_train_loader():
    base = LocalDataLoader()
    full = base.load_train().dataset
    subset = Subset(full, list(range(200)))
    return DataLoader(subset, batch_size=32, shuffle=True)


@pytest.fixture(scope="module")
def tiny_test_loader():
    base = LocalDataLoader()
    full = base.load_test().dataset
    subset = Subset(full, list(range(100)))
    return DataLoader(subset, batch_size=50, shuffle=False)


@pytest.fixture(scope="module")
def trained_classifier(tiny_train_loader):
    clf = DigitClassifier()
    clf.train(tiny_train_loader, epochs=1)
    return clf


@pytest.fixture
def sample_pixels():
    # Mid-gray uniform input — not a real digit, just a well-formed tensor source.
    return [128.0] * N_PIXELS


# ---------- MnistCNN — pure architecture, no training -----------------------------

class TestMnistCNN:
    def test_forward_pass_returns_logits_shape(self):
        model = MnistCNN()
        model.eval()
        with torch.no_grad():
            logits = model(torch.zeros(4, 1, 28, 28))
        assert logits.shape == (4, 10)

    def test_forward_pass_single_sample(self):
        model = MnistCNN()
        model.eval()
        with torch.no_grad():
            logits = model(torch.zeros(1, 1, 28, 28))
        assert logits.shape == (1, 10)

    def test_parameter_count_is_nontrivial(self):
        model = MnistCNN()
        n_params = sum(p.numel() for p in model.parameters())
        # Expected ~1.2M parameters; just sanity-check we're in the right order.
        assert 1_000_000 < n_params < 2_000_000


# ---------- DigitClassifier — train/evaluate/predict wrapper ----------------------

class TestDigitClassifier:
    def test_untrained_predict_raises(self, sample_pixels):
        clf = DigitClassifier()
        tensor = DataPreprocessor.transform_input(sample_pixels)
        with pytest.raises(RuntimeError, match="trained"):
            clf.predict(tensor)

    def test_untrained_evaluate_raises(self, tiny_test_loader):
        clf = DigitClassifier()
        with pytest.raises(RuntimeError, match="trained"):
            clf.evaluate(tiny_test_loader)

    def test_train_sets_is_trained(self, trained_classifier):
        assert trained_classifier.is_trained is True

    def test_classes_are_digit_strings(self):
        assert DigitClassifier.CLASSES == [str(i) for i in range(10)]

    def test_evaluate_returns_metrics_dict(self, trained_classifier, tiny_test_loader):
        metrics = trained_classifier.evaluate(tiny_test_loader)
        assert set(metrics.keys()) == {"accuracy", "correct", "total"}
        assert metrics["total"] == 100
        assert 0.0 <= metrics["accuracy"] <= 1.0
        assert 0 <= metrics["correct"] <= metrics["total"]

    def test_predict_returns_valid_digit(self, trained_classifier, sample_pixels):
        tensor = DataPreprocessor.transform_input(sample_pixels)
        result = trained_classifier.predict(tensor)
        assert result["prediction"] in range(10)
        assert result["digit"] == str(result["prediction"])

    def test_predict_confidence_in_unit_interval(self, trained_classifier, sample_pixels):
        tensor = DataPreprocessor.transform_input(sample_pixels)
        result = trained_classifier.predict(tensor)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_predict_probabilities_sum_to_1(self, trained_classifier, sample_pixels):
        tensor = DataPreprocessor.transform_input(sample_pixels)
        result = trained_classifier.predict(tensor)
        total = sum(result["probabilities"].values())
        assert abs(total - 1.0) < 1e-3   # small float drift OK
        assert set(result["probabilities"].keys()) == set(str(i) for i in range(10))


# ---------- PredictionService — orchestration + MLflow integration ----------------

class TestPredictionService:
    def test_train_with_tiny_subset_sets_ready(self, tiny_train_loader, tiny_test_loader):
        svc = PredictionService()
        assert svc.is_ready is False
        metrics = svc.train(epochs=1, train_loader=tiny_train_loader, test_loader=tiny_test_loader)
        assert svc.is_ready is True
        assert "accuracy" in metrics
        assert metrics["total"] == 100

    def test_get_model_info_after_train(self, tiny_train_loader, tiny_test_loader):
        svc = PredictionService()
        svc.train(epochs=1, train_loader=tiny_train_loader, test_loader=tiny_test_loader)
        info = svc.get_model_info()
        assert info["model_type"] == "MnistCNN"
        assert info["architecture"] == ARCHITECTURE
        assert info["dataset"] == "MNIST"
        assert info["parameters"]["learning_rate"] == LEARNING_RATE
        assert info["parameters"]["epochs"] == 1
        assert info["split"]["train_samples"] == 200
        assert info["split"]["test_samples"] == 100

    def test_predict_after_train_returns_digit(self, tiny_train_loader, tiny_test_loader, sample_pixels):
        svc = PredictionService()
        svc.train(epochs=1, train_loader=tiny_train_loader, test_loader=tiny_test_loader)
        result = svc.predict(sample_pixels)
        assert result["prediction"] in range(10)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_get_model_info_mlflow_url_shape_when_tracker_unavailable(
        self, tiny_train_loader, tiny_test_loader
    ):
        # Tracker isn't reachable from this test environment (no network to
        # dl-mlflow:5000); we should still get a model_info dict back, just
        # with mlflow_url=None and no run_id captured.
        svc = PredictionService()
        svc.train(epochs=1, train_loader=tiny_train_loader, test_loader=tiny_test_loader)
        info = svc.get_model_info()
        if info["run_id"] is None:
            assert info["mlflow_url"] is None
        else:
            assert info["mlflow_url"].startswith("https://mlflow-dl.pandyahomelab.com/")
