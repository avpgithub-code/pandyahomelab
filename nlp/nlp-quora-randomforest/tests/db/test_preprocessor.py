"""Tests for db-logic — question preprocessing (the L8 recipe)."""
from db_logic.transforms.preprocessor import TextPreprocessor


class TestPreprocessor:
    def test_transform_cleans_text(self):
        p = TextPreprocessor()
        raw = "Why CAN'T I earn $5,000 at 50%?? <b>[math]x[/math]</b>"
        assert p.transform(raw) == "why can not i earn dollar 5k at 50 percent x math"

    def test_shortens_big_numbers(self):
        p = TextPreprocessor()
        assert p.transform("Is 2000000 more than 3000000000?") == "is 2m more than 3b"

    def test_trace_has_one_entry_per_step(self):
        p = TextPreprocessor()
        trace = p.trace("Hello, World")
        assert [t["step"] for t in trace] == p.step_names
        assert trace[-1]["text"] == p.transform("Hello, World")
