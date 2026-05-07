import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from db_logic.loaders.loaders import LocalDataLoader
from db_logic.transforms.preprocessor import DataPreprocessor


def test_load_returns_dataframe():
    df = LocalDataLoader().load()
    assert len(df) == 20640


def test_correct_columns():
    loader = LocalDataLoader()
    df = loader.load()
    expected = loader.FEATURE_COLS + [loader.TARGET_COL]
    assert list(df.columns) == expected


def test_split_shapes():
    loader = LocalDataLoader()
    df = loader.load()
    X_train, X_test, y_train, y_test = loader.split(df)
    assert len(X_train) + len(X_test) == 20640
    assert len(X_train) == len(y_train)
    assert len(X_test) == len(y_test)


def test_preprocessor_fit_transform_shape():
    loader = LocalDataLoader()
    df = loader.load()
    X_train, _, _, _ = loader.split(df)
    result = DataPreprocessor().fit_transform(X_train)
    assert result.shape == X_train.shape


def test_scaled_mean_near_zero():
    loader = LocalDataLoader()
    df = loader.load()
    X_train, _, _, _ = loader.split(df)
    result = DataPreprocessor().fit_transform(X_train)
    import numpy as np
    assert abs(result.mean()) < 0.1
