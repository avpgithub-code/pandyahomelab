"""Tests for db-logic — text preprocessing and loading."""
from db_logic.loaders.loaders import TextLoader
from db_logic.transforms.preprocessor import TextPreprocessor


class TestPreprocessor:
    def test_transform_cleans_text(self):
        p = TextPreprocessor()
        raw = "Great <b>MOVIE</b>!!  See https://example.com now"
        assert p.transform(raw) == "great movie see now"

    def test_trace_has_one_entry_per_step(self):
        p = TextPreprocessor()
        trace = p.trace("Hello, World")
        assert [t["step"] for t in trace] == p.step_names
        assert trace[-1]["text"] == p.transform("Hello, World")


class TestLoader:
    def test_sample_corpus_shape(self):
        df = TextLoader().load()
        assert list(df.columns) == ["text", "label"]
        assert len(df) > 0

    def test_split_is_stratified(self):
        split = TextLoader().train_test_split(test_size=0.25)
        assert set(split.train["label"]) == set(split.test["label"])
