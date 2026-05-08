"""Tests for application logic layer — PyCaret AutoML service."""
import pytest
from unittest.mock import patch, MagicMock


SAMPLE_FEATURES = {
    "pclass": 1, "sex": "female", "age": 28.0,
    "sibsp": 0, "parch": 0, "fare": 100.0, "embarked": "S"
}


def _make_service_with_mock_model():
    """Build a PredictionService with PyCaret imports fully mocked."""
    import sys
    import pandas as pd

    fake_pred_df = pd.DataFrame({
        "prediction_label": [1],
        "prediction_score": [0.87],
    })

    leaderboard_df = pd.DataFrame([{
        "Model": "LogisticRegression", "Accuracy": 0.82,
        "AUC": 0.87, "F1": 0.80, "Prec.": 0.81, "Recall": 0.79,
    }] * 5)

    mock_pycaret = MagicMock()
    mock_pycaret.classification.compare_models.return_value = [MagicMock()]
    mock_pycaret.classification.pull.return_value = leaderboard_df
    mock_pycaret.classification.tune_model.return_value = MagicMock(
        __class__=type("LogisticRegression", (), {})
    )
    mock_pycaret.classification.finalize_model.return_value = MagicMock()
    mock_pycaret.classification.predict_model.return_value = fake_pred_df

    mock_mlflow = MagicMock()
    mock_mlflow.last_active_run.return_value = MagicMock(
        info=MagicMock(run_id="abc123", experiment_id="1")
    )

    sys.modules["pycaret"] = mock_pycaret
    sys.modules["pycaret.classification"] = mock_pycaret.classification
    sys.modules["mlflow"] = mock_mlflow

    with patch("db_logic.loaders.loaders.create_engine"):
        from application_logic.services.prediction_service import PredictionService
        svc = PredictionService()
        svc._loader.load = MagicMock(return_value=MagicMock())
        svc._loader._table_exists = lambda: False
        return svc, mock_pycaret


@pytest.fixture(scope="module")
def trained_service():
    svc, _ = _make_service_with_mock_model()
    svc.train()
    return svc


def test_predict_returns_valid_survival(trained_service):
    result = trained_service.predict(SAMPLE_FEATURES)
    assert result["prediction"] in (0, 1)


def test_predict_confidence_between_0_and_1(trained_service):
    result = trained_service.predict(SAMPLE_FEATURES)
    assert 0.0 <= result["confidence"] <= 1.0


def test_accuracy_above_threshold(trained_service):
    assert trained_service._metrics["accuracy"] > 0.75


def test_leaderboard_has_multiple_models(trained_service):
    assert len(trained_service._leaderboard) >= 2


def test_service_is_ready_after_train(trained_service):
    assert trained_service.is_ready is True
