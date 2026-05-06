"""Tests for DB logic layer — loaders and preprocessor."""
import numpy as np
import pytest

from db_logic.loaders.loaders import LocalDataLoader
from db_logic.transforms.preprocessor import DataPreprocessor


@pytest.fixture
def loader():
    return LocalDataLoader()


@pytest.fixture
def df(loader):
    return loader.load()


class TestLocalDataLoader:
    def test_load_returns_150_rows(self, df):
        assert len(df) == 150

    def test_load_correct_columns(self, df):
        assert list(df.columns) == [
            "sepal_length", "sepal_width", "petal_length", "petal_width", "species"
        ]

    def test_target_is_encoded(self, df):
        assert set(df["species"].unique()) == {0, 1, 2}

    def test_get_feature_names(self, loader):
        names = loader.get_feature_names()
        assert len(names) == 4
        assert "sepal_length" in names

    def test_split_shapes(self, loader, df):
        X_train, X_test, y_train, y_test = loader.split(df, test_size=0.2)
        assert len(X_train) == 120
        assert len(X_test) == 30


class TestDataPreprocessor:
    def test_fit_transform_shape(self, loader, df):
        X = loader.get_features(df)
        preprocessor = DataPreprocessor()
        X_scaled = preprocessor.fit_transform(X)
        assert X_scaled.shape == (150, 4)

    def test_scaled_mean_near_zero(self, loader, df):
        X = loader.get_features(df)
        preprocessor = DataPreprocessor()
        X_scaled = preprocessor.fit_transform(X)
        assert np.abs(X_scaled.mean(axis=0)).max() < 1e-10

    def test_transform_without_fit_raises(self, loader, df):
        X = loader.get_features(df)
        preprocessor = DataPreprocessor()
        with pytest.raises(RuntimeError):
            preprocessor.transform(X)

    def test_is_fitted_flag(self, loader, df):
        X = loader.get_features(df)
        preprocessor = DataPreprocessor()
        assert not preprocessor.is_fitted
        preprocessor.fit(X)
        assert preprocessor.is_fitted
