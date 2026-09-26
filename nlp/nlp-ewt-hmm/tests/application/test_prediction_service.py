"""Tests for application-logic — PredictionService orchestration (needs spaCy + en_core_web_sm)."""
import pytest

pytest.importorskip("spacy")

from application_logic.model.hmm import UNKNOWN_STRATEGIES  # noqa: E402
from application_logic.services.prediction_service import PredictionService  # noqa: E402
from db_logic.transforms.tagset import UNIVERSAL12  # noqa: E402


@pytest.fixture(scope="module")
def trained():
    service = PredictionService()
    service.train()
    return service


class TestTraining:
    def test_model_info_before_training_does_not_train(self):
        service = PredictionService()
        assert service.get_model_info()["metrics"] == {}
        assert not service.is_ready

    def test_train_survives_unreachable_mlflow(self, trained):
        assert trained.is_ready
        assert trained.get_model_info()["run_id"] is None

    def test_hmm_learns_the_synthetic_grammar(self, trained):
        m = trained.get_model_info()["metrics"]["hmm"]
        assert m["accuracy"] > 0.95

    def test_every_strategy_is_scored(self, trained):
        assert set(trained.get_model_info()["unknown_ladder"]) == set(UNKNOWN_STRATEGIES)

    def test_confusion_matrix_is_12_by_12_and_sums_to_test_tokens(self, trained):
        info = trained.get_model_info()
        cm = info["confusion_matrix"]
        assert cm["labels"] == UNIVERSAL12
        assert len(cm["matrix"]) == 12 and all(len(r) == 12 for r in cm["matrix"])
        total = sum(map(sum, cm["matrix"]))
        assert f"{total:,}" == info["split"]["test_tokens"]

    def test_spacy_comparison_accounts_for_every_disagreement(self, trained):
        c = trained._comparison
        assert c["hmm_right"] + c["spacy_right"] + c["neither_right"] == c["disagreements"]
        assert 0 <= c["agreement"] <= 1


class TestPredict:
    def test_shape(self, trained):
        r = trained.predict("The dog saw Alice. They can see the can!")
        assert r["tags"] == UNIVERSAL12
        assert len(r["sentences"]) == 2
        first = r["sentences"][0]
        assert [t["word"] for t in first["tokens"]] == ["The", "dog", "saw", "Alice", "."]
        n = len(first["tokens"])
        tr = first["trellis"]
        assert len(tr["shares"]) == n and len(tr["shares"][0]) == 12
        assert abs(sum(tr["shares"][0]) - 1) < 1e-3
        assert [UNIVERSAL12[j] for j in tr["path"]] == [t["hmm"] for t in first["tokens"]]

    def test_unknown_words_are_flagged(self, trained):
        tok = trained.predict("Zanzibar saw the dog.")["sentences"][0]["tokens"][0]
        assert not tok["known"] and tok["observation"] == "<UNK-CAP>"

    def test_long_input_is_truncated(self, trained):
        r = trained.predict(" ".join(["the dog saw the cat ."] * 30))
        assert r["summary"]["tokens"] == 80 and r["summary"]["truncated"]
