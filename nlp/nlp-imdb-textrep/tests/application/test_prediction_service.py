"""Tests for application-logic — representations, worked example, PredictionService."""
import pytest

from application_logic.model.representations import REPRESENTATIONS
from application_logic.model.worked_example import worked_example
from application_logic.services.prediction_service import PredictionService


@pytest.fixture(scope="module")
def trained():
    service = PredictionService()
    service.train()
    return service


class TestWorkedExample:
    def test_lecture_bow_table(self):
        bow = worked_example()["bow"]
        assert bow["columns"] == ["campusx", "comment", "people", "watch", "write"]
        assert bow["rows"][1] == [2.0, 0.0, 0.0, 1.0, 0.0]  # "campusx watch campusx"

    def test_one_hot_is_one_row_per_word(self):
        oh = worked_example()["one_hot_doc1"]
        assert len(oh["rows"]) == 3 and all(sum(r) == 1 for r in oh["rows"])


class TestPredictionService:
    def test_model_info_before_training_does_not_train(self):
        service = PredictionService()
        assert service.get_model_info()["metrics"] == {}
        assert not service.is_ready

    def test_train_survives_unreachable_mlflow(self, trained):
        assert trained.is_ready
        assert trained.get_model_info()["run_id"] is None

    def test_every_representation_is_evaluated(self, trained):
        info = trained.get_model_info()
        assert set(info["metrics"]) == set(REPRESENTATIONS) == set(info["comparison"])
        assert all(m["accuracy"] > 0.9 for m in info["metrics"].values())  # synthetic is easy

    def test_one_hot_and_bow_share_a_vocabulary(self, trained):
        c = trained.get_model_info()["comparison"]
        assert c["one_hot"]["vocabulary_size"] == c["bow"]["vocabulary_size"]
        assert c["ngram"]["vocabulary_size"] == c["tfidf"]["vocabulary_size"]

    def test_predict_explains_each_representation(self, trained):
        r = trained.predict("A wonderful film, I loved it!")
        assert r["pipeline"][-1]["step"] == "collapse_whitespace"
        assert set(r["representations"]) == set(REPRESENTATIONS)
        tfidf = r["representations"]["tfidf"]
        assert tfidf["label"] == "Positive" and tfidf["nonzeros"] > 0
        assert any(w["feature"] == "wonderful" for w in tfidf["pushes_positive"])
        assert r["representations"]["one_hot"]["top_values"][0]["value"] == 1.0

    def test_predict_negative(self, trained):
        r = trained.predict("Terrible acting, a boring film.")
        assert all(v["label"] == "Negative" for v in r["representations"].values())
