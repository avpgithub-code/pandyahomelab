"""Tests for application-logic — EmbeddingStore queries via PredictionService."""
import pytest

from application_logic.model.embeddings import MODELS, trim
from application_logic.services.prediction_service import PredictionService


@pytest.fixture(scope="module")
def svc():
    service = PredictionService()
    service.train()
    return service


def test_model_info_before_load_does_not_load():
    service = PredictionService()
    assert service.get_model_info()["comparison"] is None
    assert not service.is_ready


def test_missing_models_point_at_training(tmp_path):
    with pytest.raises(FileNotFoundError, match="train"):
        PredictionService(data_dir=str(tmp_path)).train()


def test_neighbors_cover_every_model(svc):
    r = svc.neighbors("King", topn=3)  # case-insensitive
    assert set(r) == set(MODELS)
    assert all(v["in_vocab"] and len(v["neighbors"]) == 3 for k, v in r.items() if k != "glove")


def test_fasttext_embeds_unseen_words(svc):
    r = svc.neighbors("computerr")
    assert not r["cbow"]["neighbors"] and not r["skipgram"]["neighbors"]
    assert r["fasttext"]["in_vocab"] is False and r["fasttext"]["neighbors"]


def test_analogy_reports_missing_words(svc):
    r = svc.analogy("king", "man", "zzzz")
    assert r["cbow"]["missing"] == ["zzzz"] and r["cbow"]["answers"] == []
    assert r["fasttext"]["missing"] == []


def test_similarity_and_map(svc):
    sim = svc.similarity("king", "queen")
    assert -1.0 <= sim["cbow"] <= 1.0 and sim["cbow"] is not None
    m = svc.project(["king", "queen", "computer", "zzzz"])
    assert len(m["cbow"]["points"]) == 3 and m["cbow"]["missing"] == ["zzzz"]
    assert len(m["fasttext"]["points"]) == 4


def test_comparison_rows(svc):
    c = svc.get_model_info()["comparison"]
    assert set(c) == set(MODELS)
    assert c["glove"]["train_time"] == "pretrained"


def test_trim_keeps_most_frequent_first(svc):
    kv = svc._store.models["cbow"]
    small = trim(kv, 5)
    assert small.index_to_key == kv.index_to_key[:5]
