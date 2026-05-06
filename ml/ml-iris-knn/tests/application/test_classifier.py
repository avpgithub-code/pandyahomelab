"""Tests for application logic layer — classifier and prediction service."""
import pytest

from application_logic.model.classifier import IrisClassifier
from application_logic.services.prediction_service import PredictionService
from db_logic.loaders.loaders import LocalDataLoader
from db_logic.transforms.preprocessor import DataPreprocessor


@pytest.fixture
def trained_classifier():
    loader = LocalDataLoader()
    preprocessor = DataPreprocessor()
    df = loader.load()
    X_train, X_test, y_train, y_test = loader.split(df)
    X_train_scaled = preprocessor.fit_transform(X_train)
    classifier = IrisClassifier(n_neighbors=3)
    classifier.train(X_train_scaled, y_train)
    return classifier, preprocessor, X_test, y_test


class TestIrisClassifier:
    def test_predict_returns_valid_classes(self, trained_classifier):
        classifier, preprocessor, X_test, _ = trained_classifier
        X_scaled = preprocessor.transform(X_test)
        predictions = classifier.predict(X_scaled)
        assert all(p in {0, 1, 2} for p in predictions)

    def test_predict_proba_sums_to_one(self, trained_classifier):
        classifier, preprocessor, X_test, _ = trained_classifier
        X_scaled = preprocessor.transform(X_test)
        probas = classifier.predict_proba(X_scaled)
        for row in probas:
            assert abs(sum(row) - 1.0) < 1e-6

    def test_evaluate_accuracy_above_threshold(self, trained_classifier):
        classifier, preprocessor, X_test, y_test = trained_classifier
        X_scaled = preprocessor.transform(X_test)
        result = classifier.evaluate(X_scaled, y_test)
        assert result["accuracy"] >= 0.90

    def test_predict_without_train_raises(self):
        classifier = IrisClassifier()
        with pytest.raises(RuntimeError):
            classifier.predict([[1, 2, 3, 4]])

    def test_is_trained_flag(self, trained_classifier):
        classifier, _, _, _ = trained_classifier
        assert classifier.is_trained


class TestPredictionService:
    def test_predict_returns_expected_keys(self):
        service = PredictionService()
        result = service.predict([5.1, 3.5, 1.4, 0.2])
        assert "prediction" in result
        assert "species" in result
        assert "confidence" in result
        assert "probabilities" in result

    def test_predict_setosa_features(self):
        service = PredictionService()
        result = service.predict([5.1, 3.5, 1.4, 0.2])
        assert result["species"] == "setosa"

    def test_predict_virginica_features(self):
        service = PredictionService()
        result = service.predict([6.5, 3.0, 5.8, 2.2])
        assert result["species"] == "virginica"

    def test_confidence_between_0_and_1(self):
        service = PredictionService()
        result = service.predict([5.1, 3.5, 1.4, 0.2])
        assert 0.0 <= result["confidence"] <= 1.0
