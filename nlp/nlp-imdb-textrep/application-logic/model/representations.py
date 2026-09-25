"""Four text representations, each feeding the same logistic regression (the L4 lesson).

Only the representation changes between rows; the classifier and its settings do
not, so any difference in accuracy is the representation's doing. Two vectorizers
are fit, and each is shared by a pair, so the pairs see identical vocabularies:

  one_hot  unigram counts clipped to 0/1: is the word in the review at all?
  bow      unigram counts: how many times?
  ngram    unigram + bigram counts ("not good" becomes its own column)
  tfidf    the same n-gram counts, reweighted by TF-IDF (sublinear tf)

"One-hot" in the lecture encodes each word as a vector; summed over a review and
clipped at 1 that is exactly the binary bag-of-words used here.
"""
import time
from typing import Dict, List

import joblib
import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

REPRESENTATIONS = {
    "one_hot": "One-hot (binary BoW)",
    "bow": "Bag-of-words (counts)",
    "ngram": "N-grams (1-2, counts)",
    "tfidf": "TF-IDF (1-2 grams)",
}
MIN_DF = 2
NGRAM_MAX_FEATURES = 100_000
C = 1.0
SOLVER = "liblinear"
LABELS = ["Negative", "Positive"]
TOP_K = 8


def _classifier() -> LogisticRegression:
    return LogisticRegression(C=C, solver=SOLVER, max_iter=2000)


class RepresentationSuite:
    """Fits the two shared vectorizers and one classifier per representation."""

    def __init__(self):
        self._unigram = CountVectorizer(min_df=MIN_DF)
        self._ngram = CountVectorizer(
            ngram_range=(1, 2), min_df=MIN_DF, max_features=NGRAM_MAX_FEATURES
        )
        self._tfidf = TfidfTransformer(sublinear_tf=True)
        self._models: Dict[str, LogisticRegression] = {}
        self._names: Dict[str, np.ndarray] = {}
        self.stats: Dict[str, Dict] = {}
        self.labels = LABELS

    # ——— vectors ———
    def _vectors(self, texts: List[str]) -> Dict[str, sp.csr_matrix]:
        uni = self._unigram.transform(texts)
        ng = self._ngram.transform(texts)
        return {
            "one_hot": (uni > 0).astype(np.float64),
            "bow": uni.astype(np.float64),
            "ngram": ng.astype(np.float64),
            "tfidf": self._tfidf.transform(ng),
        }

    def _feature_names(self, rep: str) -> np.ndarray:
        # Cached: get_feature_names_out() rebuilds a 100k-entry array on every call.
        key = "unigram" if rep in ("one_hot", "bow") else "ngram"
        if key not in self._names:
            vec = self._unigram if key == "unigram" else self._ngram
            self._names[key] = vec.get_feature_names_out()
        return self._names[key]

    # ——— training ———
    def fit(self, texts: List[str], y: List[int]) -> None:
        t = time.perf_counter()
        uni = self._unigram.fit_transform(texts)
        uni_seconds = time.perf_counter() - t
        t = time.perf_counter()
        ng = self._ngram.fit_transform(texts)
        ng_seconds = time.perf_counter() - t
        t = time.perf_counter()
        tfidf = self._tfidf.fit_transform(ng)
        tfidf_seconds = time.perf_counter() - t
        matrices = {
            "one_hot": ((uni > 0).astype(np.float64), uni_seconds),
            "bow": (uni.astype(np.float64), uni_seconds),
            "ngram": (ng.astype(np.float64), ng_seconds),
            "tfidf": (tfidf, ng_seconds + tfidf_seconds),
        }
        for rep, (X, vec_seconds) in matrices.items():
            t = time.perf_counter()
            self._models[rep] = _classifier().fit(X, y)
            self.stats[rep] = {
                "vocabulary_size": int(X.shape[1]),
                "density_pct": round(100.0 * X.nnz / (X.shape[0] * X.shape[1]), 3),
                "nonzeros_per_doc": round(X.nnz / X.shape[0], 1),
                "vectorize_seconds": round(vec_seconds, 1),
                "fit_seconds": round(time.perf_counter() - t, 1),
            }

    # ——— evaluation ———
    def evaluate(self, texts: List[str], y: List[int]) -> Dict[str, Dict]:
        t = time.perf_counter()
        vectors = self._vectors(texts)
        per_doc_ms = (time.perf_counter() - t) * 1000 / max(len(texts), 1)
        out = {}
        for rep, X in vectors.items():
            proba = self._models[rep].predict_proba(X)[:, 1]
            preds = (proba >= 0.5).astype(int)
            out[rep] = {
                "metrics": {
                    "accuracy": round(float(accuracy_score(y, preds)), 4),
                    "precision": round(float(precision_score(y, preds, zero_division=0)), 4),
                    "recall": round(float(recall_score(y, preds, zero_division=0)), 4),
                    "f1": round(float(f1_score(y, preds, zero_division=0)), 4),
                    "roc_auc": round(float(roc_auc_score(y, proba)), 4),
                },
                "confusion_matrix": confusion_matrix(y, preds, labels=[0, 1]).tolist(),
                # Both vectorizers run for every review, so the latency is shared.
                "transform_ms_per_doc": round(per_doc_ms, 3),
            }
        return out

    # ——— one review, explained ———
    def explain(self, text: str) -> Dict[str, Dict]:
        """Per representation: P(positive), the vector's non-zero entries and the
        words that pushed the prediction each way (weight × value)."""
        vectors = self._vectors([text])
        out = {}
        for rep, X in vectors.items():
            row = X.tocsr()
            idx, vals = row.indices, row.data
            names = self._feature_names(rep)
            coef = self._models[rep].coef_[0]
            contrib = vals * coef[idx]
            order_val = np.argsort(-vals)[:TOP_K]
            order_pos = [i for i in np.argsort(-contrib) if contrib[i] > 0][:TOP_K]
            order_neg = [i for i in np.argsort(contrib) if contrib[i] < 0][:TOP_K]
            proba = float(self._models[rep].predict_proba(X)[0, 1])
            out[rep] = {
                "name": REPRESENTATIONS[rep],
                "probability_positive": round(proba, 4),
                "label": LABELS[int(proba >= 0.5)],
                "dimensions": int(X.shape[1]),
                "nonzeros": int(len(idx)),
                "top_values": [
                    {"feature": str(names[idx[i]]), "value": round(float(vals[i]), 4)}
                    for i in order_val
                ],
                "pushes_positive": [
                    {"feature": str(names[idx[i]]), "weight": round(float(contrib[i]), 3)}
                    for i in order_pos
                ],
                "pushes_negative": [
                    {"feature": str(names[idx[i]]), "weight": round(float(contrib[i]), 3)}
                    for i in order_neg
                ],
            }
        return out

    def save(self, path: str) -> None:
        joblib.dump(
            {"unigram": self._unigram, "ngram": self._ngram, "tfidf": self._tfidf,
             "models": self._models},
            path,
            compress=3,
        )
