"""Tests for application-logic — PredictionService orchestration."""
from application_logic.services.prediction_service import PredictionService


class TestPredictionService:
    def test_model_info_before_training_does_not_train(self):
        service = PredictionService()
        info = service.get_model_info()
        assert info["metrics"] == {}
        assert not service.is_ready

    def test_train_survives_unreachable_mlflow(self):
        # conftest points MLflow at a closed port — training must still succeed.
        service = PredictionService()
        metrics = service.train()
        assert service.is_ready
        assert 0.0 <= metrics["accuracy"] <= 1.0
        assert service.get_model_info()["run_id"] is None

    def test_predict_shape(self):
        service = PredictionService()
        result = service.predict("What a wonderful story")
        assert result["label"] in result["probabilities"]
        assert abs(sum(result["probabilities"].values()) - 1.0) < 1e-3
        assert result["pipeline"][-1]["step"] == "collapse_whitespace"

    def test_confusion_matrix_matches_labels(self):
        service = PredictionService()
        service.train()
        cm = service.get_model_info()["confusion_matrix"]
        n = len(cm["labels"])
        assert len(cm["matrix"]) == n and all(len(row) == n for row in cm["matrix"])
