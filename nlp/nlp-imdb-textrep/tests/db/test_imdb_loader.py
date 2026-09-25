"""Tests for the IMDB loader against small parquet files in its schema."""
import pandas as pd
import pytest

pytest.importorskip("pyarrow")

from db_logic.loaders.imdb import IMDB_FILES, ImdbLoader, imdb_url  # noqa: E402


@pytest.fixture
def data_dir(tmp_path):
    df = pd.DataFrame({"text": [f"review {i}" for i in range(100)], "label": [i % 2 for i in range(100)]})
    df.to_parquet(tmp_path / "train.parquet")
    df.head(40).to_parquet(tmp_path / "test.parquet")
    return str(tmp_path)


def test_load_and_split(data_dir):
    split = ImdbLoader(data_dir).train_test_split()
    assert (len(split.train), len(split.test)) == (100, 40)
    assert list(split.train.columns) == ["text", "label"]


def test_subsample_is_stratified(data_dir):
    split = ImdbLoader(data_dir).train_test_split(max_train_rows=50)
    assert len(split.train) == 50 and split.train["label"].mean() == 0.5


def test_missing_file_points_at_make_data(tmp_path):
    with pytest.raises(FileNotFoundError, match="make data"):
        ImdbLoader(str(tmp_path)).load("train")


def test_urls_are_pinned_to_a_revision():
    assert all("/resolve/main/" not in imdb_url(s) for s in IMDB_FILES)
