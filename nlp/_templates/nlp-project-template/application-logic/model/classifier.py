"""Model wrapper — PLACEHOLDER: TF-IDF + logistic regression.

Swap in the demo's real model (Random Forest over engineered features, HMM,
Word2Vec, ...) but keep the interface the service relies on: fit, predict_proba,
evaluate, save, plus the ARCHITECTURE / hyper-parameter constants that
PredictionService logs to MLflow and returns from /model-info.
"""
from typing import Dict, List

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.pipeline import Pipeline

ARCHITECTURE = "TfidfVectorizer(1-2 grams) -> LogisticRegression"
NGRAM_RANGE = (1, 2)
MAX_FEATURES = 5000
C = 1.0
RANDOM_STATE = 42


class TextClassifier:
    """Vectorizer + classifier as one sklearn Pipeline."""

    def __init__(self):
        self._model = Pipeline([
            ("vectorizer", TfidfVectorizer(ngram_range=NGRAM_RANGE, max_features=MAX_FEATURES)),
            ("classifier", LogisticRegression(C=C, max_iter=1000, random_state=RANDOM_STATE)),
        ])
        self.labels: List[str] = []

    def fit(self, texts: List[str], labels: List[str]) -> None:
        self._model.fit(texts, labels)
        self.labels = [str(c) for c in self._model.classes_]

    def predict_proba(self, texts: List[str]) -> np.ndarray:
        return self._model.predict_proba(texts)

    def evaluate(self, texts: List[str], labels: List[str]) -> Dict:
        preds = self._model.predict(texts)
        precision, recall, f1, _ = precision_recall_fscore_support(
            labels, preds, average="macro", zero_division=0
        )
        cm = confusion_matrix(labels, preds, labels=self.labels)
        return {
            "metrics": {
                "accuracy": round(float(accuracy_score(labels, preds)), 4),
                "precision_macro": round(float(precision), 4),
                "recall_macro": round(float(recall), 4),
                "f1_macro": round(float(f1), 4),
            },
            "confusion_matrix": cm.tolist(),
        }

    @property
    def vocabulary_size(self) -> int:
        return len(self._model.named_steps["vectorizer"].vocabulary_)

    def save(self, path: str) -> None:
        joblib.dump(self._model, path)
