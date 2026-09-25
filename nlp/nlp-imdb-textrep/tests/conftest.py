"""Pytest configuration — adds project root to sys.path so the symlinked
db_logic / application_logic / presentation_logic packages resolve without
needing PYTHONPATH=/app in the environment.

IMDB_DATA_DIR points at a small synthetic dataset in the IMDB parquet schema,
written once per session, so tests never need `make data`.

MLflow points at a closed local port with retries off, so every test exercises
the graceful-degradation path quickly instead of waiting on HTTP back-off.
"""
import os
import random
import sys
import tempfile

import pandas as pd

os.environ["MLFLOW_TRACKING_URI"] = "http://127.0.0.1:9"
os.environ["MLFLOW_HTTP_REQUEST_MAX_RETRIES"] = "0"
os.environ["MLFLOW_HTTP_REQUEST_TIMEOUT"] = "2"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


_POS = ["a wonderful film", "great acting", "i loved it", "brilliant and moving", "superb story"]
_NEG = ["a boring film", "terrible acting", "i hated it", "dull and predictable", "awful story"]
_FILL = ["the plot", "this movie", "the director", "the cast", "the ending", "overall"]


def _synthetic_imdb(n: int, seed: int) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        label = i % 2
        words = _POS if label else _NEG
        text = f"{rng.choice(_FILL)} was {rng.choice(words)}.<br /><br />{rng.choice(_FILL)}: {rng.choice(words)}!"
        rows.append({"text": text, "label": label})
    return pd.DataFrame(rows)


_IMDB_DIR = tempfile.mkdtemp(prefix="imdb-test-")
_synthetic_imdb(200, seed=1).to_parquet(os.path.join(_IMDB_DIR, "train.parquet"))
_synthetic_imdb(60, seed=2).to_parquet(os.path.join(_IMDB_DIR, "test.parquet"))
os.environ["IMDB_DATA_DIR"] = _IMDB_DIR
