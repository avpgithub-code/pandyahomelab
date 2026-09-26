"""Pytest configuration — adds project root to sys.path so the symlinked
db_logic / application_logic / presentation_logic packages resolve without
needing PYTHONPATH=/app in the environment.

DATA_DIR points at a tiny data/models tree trained here on a synthetic corpus
(the real one takes ~35 min), so tests never need text8, GloVe or `make train`.

MLflow points at a closed local port with retries off, so every test exercises
the graceful-degradation path quickly instead of waiting on HTTP back-off.
"""
import json
import os
import random
import sys
import tempfile

os.environ["MLFLOW_TRACKING_URI"] = "http://127.0.0.1:9"
os.environ["MLFLOW_HTTP_REQUEST_MAX_RETRIES"] = "0"
os.environ["MLFLOW_HTTP_REQUEST_TIMEOUT"] = "2"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from application_logic.model.embeddings import MODELS, TRAINED, train_model, trim  # noqa: E402

_ROYAL = ["king", "queen", "prince", "princess", "throne", "crown"]
_PEOPLE = ["man", "woman", "boy", "girl", "father", "mother"]
_TECH = ["computer", "software", "hardware", "program", "code", "data"]


def _corpus(n: int = 600, seed: int = 1):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        group = rng.choice([_ROYAL, _PEOPLE, _TECH])
        out.append([rng.choice(group) for _ in range(8)] + ["the", "and", "of"])
    return out


_DATA_DIR = tempfile.mkdtemp(prefix="w2v-test-")
_MODELS = os.path.join(_DATA_DIR, "models")
os.makedirs(_MODELS)
_sentences = _corpus()
_results = {}
for _name in TRAINED:
    _kv, _secs = train_model(_name, _sentences, workers=1, min_count=1, epochs=3)
    _kv.save(os.path.join(_MODELS, f"{_name}.kv"))
    _results[_name] = {"train_seconds": round(_secs, 2), "vocabulary_size": len(_kv.key_to_index),
                       "analogy_semantic": 0.1, "analogy_syntactic": 0.2, "analogy_total": 0.15,
                       "analogy_questions": 100, "wordsim_spearman": 0.5, "wordsim_oov_pct": 90.0,
                       "size_mb": 0.1}
# Stand-in for GloVe: the CBOW vectors, trimmed like the real reference.
_kv, _ = train_model("cbow", _sentences, workers=1, min_count=1, epochs=3)
trim(_kv, 15).save(os.path.join(_MODELS, "glove.kv"))
_results["glove"] = {**_results["cbow"], "train_seconds": None, "vocabulary_size": 15}
with open(os.path.join(_MODELS, "metrics.json"), "w") as _f:
    json.dump({"trained_at": "2026-09-25T00:00:00Z", "corpus": {"name": "synthetic", "tokens": 6600},
               "reference": {"name": "stand-in", "kept_words": 15},
               "params": {"vector_size": 100, "window": 5, "min_count": 1, "negative": 5,
                          "epochs": 3, "fasttext_bucket": 200000, "workers": 1},
               "models": _results}, _f)
assert set(_results) == set(MODELS)
os.environ["DATA_DIR"] = _DATA_DIR
