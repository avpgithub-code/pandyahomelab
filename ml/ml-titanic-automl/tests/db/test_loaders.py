"""Tests for DB layer — Titanic loader with PostgreSQL persistence."""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock


@pytest.fixture(scope="module")
def loader_with_mock_db():
    """LocalDataLoader with DB mocked to return seaborn data directly."""
    with patch("db_logic.loaders.loaders.create_engine"):
        from db_logic.loaders.loaders import LocalDataLoader
        loader = LocalDataLoader()
        # Force download path (no table in DB)
        loader._table_exists = lambda: False
        loader._engine = MagicMock()
        # Stub to_sql so it doesn't actually write
        with patch.object(pd.DataFrame, "to_sql"):
            yield loader


def test_load_returns_dataframe(loader_with_mock_db):
    df = loader_with_mock_db.load()
    assert isinstance(df, pd.DataFrame)


def test_correct_columns(loader_with_mock_db):
    df = loader_with_mock_db.load()
    expected = {"pclass", "sex", "age", "sibsp", "parch", "fare", "embarked", "survived"}
    assert expected.issubset(set(df.columns))


def test_no_nulls_after_clean(loader_with_mock_db):
    df = loader_with_mock_db.load()
    assert df.isnull().sum().sum() == 0


def test_survived_is_binary(loader_with_mock_db):
    df = loader_with_mock_db.load()
    assert set(df["survived"].unique()).issubset({0, 1})
