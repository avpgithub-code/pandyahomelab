"""Pytest configuration — adds project root to sys.path so the symlinked
db_logic / application_logic / presentation_logic packages resolve without
needing PYTHONPATH=/app in the environment.

QQP_DATA_DIR points at a small synthetic dataset in GLUE's parquet schema,
written once per session, so tests never need `make data` or the real licence-
restricted files.

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


_TOPICS = ["python", "java", "cooking", "football", "guitar", "physics", "history", "chess",
           "painting", "running", "investing", "gardening"]


def _synthetic_qqp(n: int, seed: int) -> pd.DataFrame:
    """Duplicates reword the same topic; non-duplicates ask about two topics."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        a = rng.choice(_TOPICS)
        if i % 3 == 0:
            q1, q2, label = f"How do I learn {a} fast?", f"What is the fastest way to learn {a}?", 1
        else:
            b = rng.choice([t for t in _TOPICS if t != a])
            q1, q2, label = f"How do I learn {a} fast?", f"Why is {b} so hard to master?", 0
        rows.append({"question1": q1, "question2": q2, "label": label, "idx": i})
    return pd.DataFrame(rows)


_QQP_DIR = tempfile.mkdtemp(prefix="qqp-test-")
_synthetic_qqp(240, seed=1).to_parquet(os.path.join(_QQP_DIR, "train.parquet"))
_synthetic_qqp(60, seed=2).to_parquet(os.path.join(_QQP_DIR, "validation.parquet"))
os.environ["QQP_DATA_DIR"] = _QQP_DIR
os.environ["QQP_MAX_TRAIN_ROWS"] = "0"
