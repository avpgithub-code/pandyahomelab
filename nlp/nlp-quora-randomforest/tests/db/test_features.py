"""Tests for the 22 L8 question-pair features."""
import pytest

from db_logic.transforms.features import FEATURE_GROUPS, FEATURE_NAMES, PairFeatureBuilder

STOPS = frozenset({"how", "do", "i", "the", "a", "to", "is", "what"})


@pytest.fixture
def fb():
    return PairFeatureBuilder(stopwords=STOPS)


def test_feature_count_matches_the_lecture():
    sizes = {group: len(names) for group, names in FEATURE_GROUPS.items()}
    assert sizes == {"basic": 7, "token": 8, "length": 3, "fuzzy": 4}
    assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES)) == 22


def test_identical_questions(fb):
    f = fb.build("how do i learn python", "how do i learn python")
    assert f["word_share"] == 0.5
    assert f["cwc_min"] == pytest.approx(1.0, abs=1e-3)
    assert f["ctc_max"] == pytest.approx(1.0, abs=1e-3)
    assert f["first_word_eq"] == f["last_word_eq"] == 1.0
    assert f["abs_len_diff"] == 0.0
    assert f["fuzz_ratio"] == f["token_set_ratio"] == 100.0
    assert f["longest_substr_ratio"] == pytest.approx(21 / 22)


def test_token_features_split_stopwords_from_content_words(fb):
    # content words: {learn, python} vs {learn, java}; stopwords: {how, do, i} both
    f = fb.build("how do i learn python", "how do i learn java")
    assert f["cwc_min"] == pytest.approx(0.5, abs=1e-3)
    assert f["csc_min"] == pytest.approx(1.0, abs=1e-3)
    assert f["last_word_eq"] == 0.0


def test_empty_question_does_not_divide_by_zero(fb):
    f = fb.build("", "what is love")
    assert set(f) == set(FEATURE_NAMES)
    assert f["cwc_min"] == f["mean_len"] == f["word_share"] == 0.0


def test_matrix_columns_follow_feature_names(fb):
    m = fb.build_matrix(["how do i learn python"], ["how do i learn java"])
    assert m.shape == (1, 22)
    assert m[0, FEATURE_NAMES.index("q1_num_words")] == 5
