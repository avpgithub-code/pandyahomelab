"""Model: the L8 recipe, bag-of-words (3000 × 2 questions) + 22 features -> Random Forest.

The CountVectorizer is fit on q1 + q2 together (one shared vocabulary), then each
question is transformed separately, so column i means the same word on both
sides. The feature matrix stays sparse end to end: 6022 columns × 100k rows
dense would be ~2.4 GB of float32; sparse it is a few tens of MB.
"""
from typing import Dict, List

import joblib
import numpy as np
import scipy.sparse as sp
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

ARCHITECTURE = "BoW(3000) × 2 questions + 22 engineered features -> RandomForestClassifier"
BOW_MAX_FEATURES = 3000
N_ESTIMATORS = 100
MIN_SAMPLES_LEAF = 2  # 100k rows: 80.2% acc, 88 MB model, 202 s fit (leaf=1: 80.8%, 388 MB, 533 s)
N_JOBS = 2
RANDOM_STATE = 42
LABELS = ["Not duplicate", "Duplicate"]


class DuplicateClassifier:
    """Shared-vocabulary BoW + handcrafted features into a Random Forest."""

    def __init__(self):
        self._bow = CountVectorizer(max_features=BOW_MAX_FEATURES)
        self._rf = RandomForestClassifier(
            n_estimators=N_ESTIMATORS,
            min_samples_leaf=MIN_SAMPLES_LEAF,
            n_jobs=N_JOBS,
            random_state=RANDOM_STATE,
        )
        self.labels = LABELS

    def fit(self, q1s: List[str], q2s: List[str], handcrafted: np.ndarray, y: List[int]) -> None:
        self._bow.fit(q1s + q2s)
        self._rf.fit(self._matrix(q1s, q2s, handcrafted), y)

    def predict_proba(self, q1s: List[str], q2s: List[str], handcrafted: np.ndarray) -> np.ndarray:
        """P(duplicate) per pair. The threshold is the caller's choice (the UI slider)."""
        return self._rf.predict_proba(self._matrix(q1s, q2s, handcrafted))[:, 1]

    def evaluate(
        self, q1s: List[str], q2s: List[str], handcrafted: np.ndarray, y: List[int],
        threshold: float = 0.5,
    ) -> Dict:
        proba = self.predict_proba(q1s, q2s, handcrafted)
        preds = (proba >= threshold).astype(int)
        return {
            "metrics": {
                "accuracy": round(float(accuracy_score(y, preds)), 4),
                "precision": round(float(precision_score(y, preds, zero_division=0)), 4),
                "recall": round(float(recall_score(y, preds, zero_division=0)), 4),
                "f1": round(float(f1_score(y, preds, zero_division=0)), 4),
                "roc_auc": round(float(roc_auc_score(y, proba)), 4),
                "log_loss": round(float(log_loss(y, proba, labels=[0, 1])), 4),
            },
            "confusion_matrix": confusion_matrix(y, preds, labels=[0, 1]).tolist(),
        }

    def _matrix(self, q1s: List[str], q2s: List[str], handcrafted: np.ndarray) -> sp.csr_matrix:
        return sp.hstack(
            [sp.csr_matrix(handcrafted), self._bow.transform(q1s), self._bow.transform(q2s)]
        ).tocsr()

    @property
    def vocabulary_size(self) -> int:
        return len(self._bow.vocabulary_)

    def save(self, path: str) -> None:
        joblib.dump({"bow": self._bow, "rf": self._rf}, path, compress=3)
