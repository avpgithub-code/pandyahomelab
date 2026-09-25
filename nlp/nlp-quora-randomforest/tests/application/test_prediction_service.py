"""Tests for application-logic — PredictionService orchestration (synthetic QQP from conftest)."""
import pytest

from application_logic.services.prediction_service import PredictionService
from db_logic.transforms.features import FEATURE_GROUPS


@pytest.fixture(scope="module")
def trained():
    service = PredictionService()
    service.train()
    return service


class TestPredictionService:
    def test_model_info_before_training_does_not_train(self):
        service = PredictionService()
        info = service.get_model_info()
        assert info["metrics"] == {}
        assert not service.is_ready

    def test_train_survives_unreachable_mlflow(self, trained):
        # conftest points MLflow at a closed port — training must still succeed.
        assert trained.is_ready
        assert trained.get_model_info()["run_id"] is None

    def test_metrics_cover_the_plan(self, trained):
        m = trained.get_model_info()["metrics"]
        assert set(m) == {"accuracy", "precision", "recall", "f1", "roc_auc", "log_loss"}
        assert m["accuracy"] > 0.9  # the synthetic pairs are easy

    def test_predict_shape(self, trained):
        r = trained.predict("How do I learn chess fast?", "What is the fastest way to learn chess?")
        assert 0.0 <= r["probability"] <= 1.0
        assert r["label"] == ("Duplicate" if r["probability"] >= r["threshold"] else "Not duplicate")
        assert {g: list(v) for g, v in r["features"].items()} == FEATURE_GROUPS
        assert r["pipeline"]["question2"][-1]["step"] == "collapse_whitespace"

    def test_duplicate_scores_above_non_duplicate(self, trained):
        dup = trained.predict("How do I learn chess fast?", "What is the fastest way to learn chess?")
        diff = trained.predict("How do I learn chess fast?", "Why is cooking so hard to master?")
        assert dup["probability"] > diff["probability"]

    def test_confusion_matrix_is_2x2_with_named_labels(self, trained):
        cm = trained.get_model_info()["confusion_matrix"]
        assert cm["labels"] == ["Not duplicate", "Duplicate"]
        assert len(cm["matrix"]) == 2 and all(len(row) == 2 for row in cm["matrix"])
        assert sum(map(sum, cm["matrix"])) == trained.get_model_info()["split"]["test_samples"]
