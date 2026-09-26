"""Tests for the hand-built HMM: counting, Viterbi, trellis and unknown-word strategies."""
import numpy as np
import pytest

from application_logic.model.hmm import UNK, HmmTagger, signature

TAGS = ["DET", "NOUN", "VERB", "PRON", "."]
CORPUS = [
    [("the", "DET"), ("can", "NOUN"), ("fell", "VERB"), (".", ".")],
    [("the", "DET"), ("dog", "NOUN"), ("ran", "VERB"), (".", ".")],
    [("the", "DET"), ("dog", "NOUN"), ("fell", "VERB"), (".", ".")],
    [("we", "PRON"), ("can", "VERB"), ("run", "VERB"), (".", ".")],
    [("they", "PRON"), ("can", "VERB"), ("run", "VERB"), (".", ".")],
    [("the", "DET"), ("Walking", "NOUN"), ("ran", "VERB"), (".", ".")],
]


@pytest.fixture
def hmm():
    return HmmTagger("signatures").fit(CORPUS, tags=TAGS)


def test_probability_tables_are_distributions(hmm):
    assert np.isclose(np.exp(hmm.log_start).sum(), 1.0)
    assert np.allclose(np.exp(hmm.log_trans).sum(1), 1.0)
    assert np.allclose(np.exp(hmm.log_emit).sum(1), 1.0)


def test_counts(hmm):
    ti = {t: i for i, t in enumerate(TAGS)}
    assert hmm.start_counts[ti["DET"]] == 4 and hmm.start_counts[ti["PRON"]] == 2
    assert hmm.trans_counts[ti["DET"], ti["NOUN"]] == 4


def test_transitions_resolve_ambiguity(hmm):
    # Same word, different tag, decided by the previous tag.
    assert hmm.tag(["the", "can", "fell", "."]) == ["DET", "NOUN", "VERB", "."]
    assert hmm.tag(["we", "can", "run", "."]) == ["PRON", "VERB", "VERB", "."]


def test_backpointers_trace_the_best_path(hmm):
    v = hmm.viterbi(["the", "dog", "ran", "."])
    assert v["trellis"].shape == (4, len(TAGS))
    path = v["path"]
    for i in range(len(path) - 1, 0, -1):
        assert v["back"][i][path[i]] == path[i - 1]
    assert path[-1] == int(v["trellis"][-1].argmax())


def test_empty_input(hmm):
    assert hmm.tag([]) == []


def test_signatures():
    assert signature("running") == "<UNK-ing>"
    assert signature("Kowalski") == "<UNK-CAP>"
    assert signature("Tuesdays") == "<UNK-CAP-s>"
    assert signature("3,400") == "<UNK-NUM>"
    assert signature("--") == "<UNK-PUNCT>"
    assert signature("well-known") == "<UNK-HYPH>"


def test_unknown_word_reads_its_class(hmm):
    assert hmm.observation("dog") == "dog"
    # Seen once in training -> rewritten to its class, just like an unseen word.
    assert hmm.observation("fell") == "fell"
    assert hmm.observation("Walking") == "<UNK-CAP-ing>"
    assert hmm.observation("zebra") == "<UNK>"
    assert "zebra" not in hmm.known and "Walking" in hmm.known


def test_strategies_differ_in_their_columns():
    lap = HmmTagger("laplace").fit(CORPUS, tags=TAGS)
    unk = HmmTagger("unk").fit(CORPUS, tags=TAGS)
    sig = HmmTagger("signatures").fit(CORPUS, tags=TAGS)
    assert lap.observation("Walking") == "Walking"   # every training word is vocabulary
    assert unk.observation("Walking") == UNK
    assert lap.vocabulary_size > unk.vocabulary_size == sig.vocabulary_size
    assert sig.n_columns > unk.n_columns


def test_unknown_strategy_is_validated():
    with pytest.raises(ValueError):
        HmmTagger("nope")


def test_inspection_helpers(hmm, tmp_path):
    top = hmm.top_emissions(k=2)
    assert top["DET"][0]["word"] == "the"
    assert all(not e["word"].startswith("<UNK") for rows in top.values() for e in rows)
    assert hmm.top_signatures()[0]["class"].startswith("<UNK")
    assert len(hmm.transition_matrix()) == len(TAGS)
    hmm.save(str(tmp_path / "hmm.npz"))
    assert (tmp_path / "hmm.npz").stat().st_size > 0
