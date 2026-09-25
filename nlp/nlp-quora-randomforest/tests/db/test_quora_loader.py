"""Tests for the GLUE QQP loader, against small parquet files in GLUE's schema."""
import pandas as pd
import pytest

pytest.importorskip("pyarrow")

from db_logic.loaders.quora import COLUMNS, QQP_FILES, QuoraPairLoader, qqp_url  # noqa: E402


def _glue_frame(n: int, dup_every: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "question1": [f"How do I learn topic {i}?" for i in range(n)],
            "question2": [f"What is the best way to learn topic {i}?" for i in range(n)],
            "label": [1 if i % dup_every == 0 else 0 for i in range(n)],
            "idx": list(range(n)),
        }
    )


@pytest.fixture
def data_dir(tmp_path):
    _glue_frame(300).to_parquet(tmp_path / "train.parquet")
    _glue_frame(60).to_parquet(tmp_path / "validation.parquet")
    return str(tmp_path)


class TestQuoraPairLoader:
    def test_load_renames_to_lecture_columns(self, data_dir):
        df = QuoraPairLoader(data_dir).load("train")
        assert list(df.columns) == COLUMNS
        assert len(df) == 300

    def test_load_drops_blank_and_missing_questions(self, tmp_path):
        df = _glue_frame(5)
        df.loc[1, "question1"] = "   "
        df.loc[2, "question2"] = None
        df.to_parquet(tmp_path / "train.parquet")
        assert len(QuoraPairLoader(str(tmp_path)).load("train")) == 3

    def test_missing_file_points_at_make_data(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="make data"):
            QuoraPairLoader(str(tmp_path)).load("train")

    def test_split_uses_validation_as_test(self, data_dir):
        split = QuoraPairLoader(data_dir).train_test_split()
        assert (len(split.train), len(split.test)) == (300, 60)

    def test_subsample_keeps_duplicate_rate(self, data_dir):
        split = QuoraPairLoader(data_dir).train_test_split(max_train_rows=150, max_test_rows=30)
        assert (len(split.train), len(split.test)) == (150, 30)
        assert split.train["is_duplicate"].mean() == pytest.approx(1 / 3, abs=0.01)

    def test_subsample_is_reproducible(self, data_dir):
        a = QuoraPairLoader(data_dir).train_test_split(max_train_rows=100, seed=7).train
        b = QuoraPairLoader(data_dir).train_test_split(max_train_rows=100, seed=7).train
        pd.testing.assert_frame_equal(a, b)


def test_urls_are_pinned_to_a_revision():
    for split in QQP_FILES:
        assert "/resolve/main/" not in qqp_url(split)
