"""Embedding service: loads the offline-trained vectors and answers explorer queries.

Unlike 3a/3b there is no training at startup: training takes ~35 min on the NAS, so
scripts/train_embeddings.py runs offline, logs to nlp-mlflow and saves the vectors.
Warm-up only memory-maps them (seconds). The class keeps the template's name and
shape (train/is_ready/get_model_info) so main.py's eager warm-up is unchanged.
"""
import logging
import threading
from typing import Dict, List, Optional

from application_logic.model.embeddings import (
    ANALOGY_VOCAB,
    MODELS,
    EmbeddingStore,
)
from db_logic.loaders.sources import models_dir
from shared.config import get_config

logger = logging.getLogger(__name__)

_config = get_config()
_MLFLOW_PUBLIC_BASE = _config.MLFLOW_PUBLIC_BASE_URL
_EXPERIMENT = "nlp-text8-word2vec"
ARCHITECTURE = "Word2Vec CBOW vs skip-gram vs fastText on text8, GloVe 6B as reference (100-d each)"


def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


class PredictionService:
    """Loads the four models once, then serves neighbours, analogies, similarity and maps."""

    def __init__(self, data_dir: Optional[str] = None):
        self._store = EmbeddingStore(models_dir(data_dir or _config.DATA_DIR))
        self._ready = False
        self._lock = threading.Lock()

    def train(self) -> Dict:
        """Load, not train (see module docstring). Named for the warm-up contract."""
        with self._lock:
            if not self._ready:
                self._store.load()
                self._ready = True
            return self._store.metrics

    def _ensure(self) -> None:
        if not self._ready:
            self.train()

    def neighbors(self, word: str, topn: int = 10) -> Dict:
        self._ensure()
        return self._store.neighbors(word, topn)

    def analogy(self, a: str, b: str, c: str) -> Dict:
        self._ensure()
        return self._store.analogy(a, b, c)

    def similarity(self, w1: str, w2: str) -> Dict:
        self._ensure()
        return self._store.similarity(w1, w2)

    def project(self, words: List[str]) -> Dict:
        self._ensure()
        return self._store.project(words)

    def _comparison(self) -> Dict:
        rows = {}
        for name, label in MODELS.items():
            m = self._store.metrics["models"][name]
            rows[name] = {
                "name": label,
                "analogy_semantic": _pct(m["analogy_semantic"]),
                "analogy_syntactic": _pct(m["analogy_syntactic"]),
                "analogy_total": _pct(m["analogy_total"]),
                "wordsim_spearman": f"{m['wordsim_spearman']:.3f}",
                "vocabulary_size": f"{m['vocabulary_size']:,}",
                "train_time": "pretrained" if m["train_seconds"] is None else f"{m['train_seconds'] / 60:.1f} min",
                "size_mb": f"{m['size_mb']:.0f} MB",
            }
        return rows

    def get_model_info(self) -> Dict:
        """Model metadata for the About drawer and Model Card. Never loads or trains."""
        info = {
            "model_type": "Word embeddings × 4",
            "architecture": ARCHITECTURE,
            "dataset": "text8 (first 10^8 bytes of English Wikipedia)",
            "target": "100-d word vectors",
            "parameters": {},
            "preprocessing": {"steps": ["text8 is pre-cleaned: lowercase a-z and spaces only"]},
            "models": MODELS,
            "metrics": {},
            "metrics_display": {},
            "comparison": None,
            "confusion_matrix": None,
            "split": None,
            "training": None,
            "run_id": None,
            "experiment_id": None,
            "mlflow_url": f"{_MLFLOW_PUBLIC_BASE}/",
        }
        if not self._ready:
            return info
        mx = self._store.metrics
        best_trained = max(("cbow", "skipgram", "fasttext"),
                           key=lambda n: mx["models"][n]["wordsim_spearman"])
        info.update({
            "parameters": mx["params"],
            "metrics": mx["models"],
            "metrics_display": {
                "best_wordsim": MODELS[best_trained],
                "analogy_vocab": f"{ANALOGY_VOCAB:,}",
                "analogy_questions": f"{mx['models']['cbow']['analogy_questions']:,}",
            },
            "comparison": self._comparison(),
            "split": {"corpus_tokens": f"{mx['corpus']['tokens']:,}"},
            "training": {"trained_at": mx["trained_at"],
                         "workers": mx["params"]["workers"]},
        })
        return info

    @property
    def is_ready(self) -> bool:
        return self._ready
