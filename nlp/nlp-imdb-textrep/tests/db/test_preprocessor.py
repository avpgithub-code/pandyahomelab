"""Tests for db-logic — L3 preprocessing and the spaCy/NLTK token view."""
import pytest

from db_logic.transforms.preprocessor import TextPreprocessor


class TestPreprocessor:
    def test_transform_cleans_review(self):
        raw = "OMG this movie was GR8!!<br /><br />See www.imdb.com 😍 tbh"
        assert TextPreprocessor().transform(raw) == "oh my god this movie was great see to be honest"

    def test_chat_words_match_whole_words_only(self):
        assert TextPreprocessor().transform("Utah lol") == "utah laughing out loud"

    def test_keeps_negation(self):
        assert "not" in TextPreprocessor().transform("It was NOT good.").split()

    def test_trace_has_one_entry_per_step(self):
        p = TextPreprocessor()
        trace = p.trace("Hello, World")
        assert [t["step"] for t in trace] == p.step_names
        assert trace[-1]["text"] == p.transform("Hello, World")


class TestTokenAnalyzer:
    @pytest.fixture(scope="class")
    def analyzer(self):
        pytest.importorskip("spacy")
        from db_logic.transforms.tokens import TokenAnalyzer

        return TokenAnalyzer()

    def test_stem_vs_lemma(self, analyzer):
        rows = {r["token"]: r for r in analyzer.analyze("The studies were better")["tokens"]}
        assert rows["studies"]["stem"] == "studi"
        assert rows["studies"]["lemma"] == "study"
        assert rows["The"]["is_stop"] and not rows["studies"]["is_stop"]

    def test_counts_and_limit(self, analyzer):
        out = analyzer.analyze("one two three four", limit=2)
        assert out["total"] == 4 and len(out["tokens"]) == 2
