import sys
import os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from application_logic.model.classifier import HousingRegressor
from db_logic.loaders.loaders import LocalDataLoader
from db_logic.transforms.preprocessor import DataPreprocessor


@pytest.fixture(scope="module")
def trained_regressor():
    loader = LocalDataLoader()
    df = loader.load()
    X_train, X_test, y_train, y_test = loader.split(df)
    preprocessor = DataPreprocessor()
    X_train_scaled = preprocessor.fit_transform(X_train)
    X_test_scaled = preprocessor.transform(X_test)
    regressor = HousingRegressor()
    regressor.train(X_train_scaled, y_train)
    return regressor, X_test_scaled, y_test


def test_predict_returns_float(trained_regressor):
    regressor, X_test, _ = trained_regressor
    result = regressor.predict(X_test[:1])
    assert isinstance(result[0], float)


def test_predict_positive_value(trained_regressor):
    regressor, X_test, _ = trained_regressor
    result = regressor.predict(X_test[:1])
    assert result[0] > 0


def test_r2_score_above_threshold(trained_regressor):
    regressor, X_test, y_test = trained_regressor
    metrics = regressor.evaluate(X_test, y_test)
    assert metrics["r2"] > 0.55


def test_predict_without_train_raises():
    regressor = HousingRegressor()
    with pytest.raises(RuntimeError):
        regressor.predict([[1, 2, 3, 4, 5, 6, 7, 8]])
