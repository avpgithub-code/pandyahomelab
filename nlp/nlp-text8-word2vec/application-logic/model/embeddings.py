"""Word embeddings: train, evaluate, trim, and serve (the L5 lesson).

Three models are trained on the same corpus with the same settings, so only the
algorithm differs:
  cbow      Word2Vec CBOW: predict a word from its context window
  skipgram  Word2Vec skip-gram: predict the context from the word
  fasttext  skip-gram over character n-grams (3-6), so unseen words still get a vector
GloVe 6B 100d is a pretrained reference (6B tokens vs text8's 17M), trimmed to the
most frequent 50k words.

Training takes ~35 min on the NAS, so it runs offline (scripts/train_embeddings.py)
and the service only loads the saved KeyedVectors at startup.
"""
import json
import os
import time
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from gensim.models import FastText, KeyedVectors, Word2Vec

MODELS = {
    "cbow": "Word2Vec · CBOW",
    "skipgram": "Word2Vec · skip-gram",
    "fasttext": "fastText · skip-gram + subwords",
    "glove": "GloVe 6B (pretrained reference)",
}
TRAINED = ("cbow", "skipgram", "fasttext")

VECTOR_SIZE = 100
WINDOW = 5
MIN_COUNT = 5
NEGATIVE = 5
EPOCHS = 5
SEED = 42
# fastText hashes character n-grams into this many rows. gensim's default (2M) makes
# a 830 MB model; 200k keeps it near 110 MB.
FASTTEXT_BUCKET = 200_000
GLOVE_KEEP = 50_000
# Analogy questions are asked only over the most frequent words, same for every model.
ANALOGY_VOCAB = 30_000
METRICS_FILE = "metrics.json"


def train_model(name: str, sentences: Iterable, workers: int = 3,
                min_count: int = MIN_COUNT, epochs: int = EPOCHS) -> Tuple[KeyedVectors, float]:
    common = dict(vector_size=VECTOR_SIZE, window=WINDOW, min_count=min_count,
                  negative=NEGATIVE, epochs=epochs, workers=workers, seed=SEED)
    start = time.perf_counter()
    if name == "cbow":
        model = Word2Vec(sentences=sentences, sg=0, **common)
    elif name == "skipgram":
        model = Word2Vec(sentences=sentences, sg=1, **common)
    elif name == "fasttext":
        model = FastText(sentences=sentences, sg=1, min_n=3, max_n=6,
                         bucket=FASTTEXT_BUCKET, **common)
    else:
        raise ValueError(name)
    return model.wv, time.perf_counter() - start


def trim(kv: KeyedVectors, keep: int = GLOVE_KEEP) -> KeyedVectors:
    """Keep the first `keep` words (GloVe is stored most-frequent first)."""
    out = KeyedVectors(vector_size=kv.vector_size)
    words = kv.index_to_key[:keep]
    out.add_vectors(words, np.asarray(kv.vectors[:keep]))
    return out


def evaluate(kv: KeyedVectors, analogies_path: str, wordsim_path: str) -> Dict:
    """Google analogy set split into semantic and syntactic sections, plus WordSim-353."""
    _, sections = kv.evaluate_word_analogies(analogies_path, restrict_vocab=ANALOGY_VOCAB)
    sem_ok = sem_n = syn_ok = syn_n = 0
    for s in sections:
        if s["section"] == "Total accuracy":
            continue
        ok, n = len(s["correct"]), len(s["correct"]) + len(s["incorrect"])
        if s["section"].startswith("gram"):
            syn_ok, syn_n = syn_ok + ok, syn_n + n
        else:
            sem_ok, sem_n = sem_ok + ok, sem_n + n
    pearson, spearman, oov_pct = kv.evaluate_word_pairs(wordsim_path)
    return {
        "analogy_semantic": round(sem_ok / sem_n, 4) if sem_n else 0.0,
        "analogy_syntactic": round(syn_ok / syn_n, 4) if syn_n else 0.0,
        "analogy_total": round((sem_ok + syn_ok) / (sem_n + syn_n), 4) if sem_n + syn_n else 0.0,
        "analogy_questions": sem_n + syn_n,
        "wordsim_spearman": round(float(spearman[0]), 4),
        "wordsim_oov_pct": round(float(oov_pct), 1),
    }


class EmbeddingStore:
    """Loads the saved KeyedVectors (memory-mapped) and answers the explorer's queries."""

    def __init__(self, models_dir: str):
        self._dir = models_dir
        self.models: Dict[str, KeyedVectors] = {}
        self.metrics: Dict = {}

    def load(self) -> None:
        path = os.path.join(self._dir, METRICS_FILE)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"{path} not found. Train first: scripts/train_embeddings.py (make train)."
            )
        with open(path) as f:
            self.metrics = json.load(f)
        for name in MODELS:
            # mmap: the vectors stay on disk and are paged in on use.
            self.models[name] = KeyedVectors.load(os.path.join(self._dir, f"{name}.kv"), mmap="r")

    @staticmethod
    def _norm(word: str) -> str:
        # text8 and GloVe are both lowercase.
        return word.strip().lower()

    def _has(self, name: str, word: str) -> bool:
        return word in self.models[name].key_to_index

    def _can_embed(self, name: str, word: str) -> bool:
        # fastText builds a vector for any word from its character n-grams.
        return self._has(name, word) or name == "fasttext"

    def neighbors(self, word: str, topn: int = 10) -> Dict[str, Dict]:
        word = self._norm(word)
        out = {}
        for name, kv in self.models.items():
            if not self._can_embed(name, word):
                out[name] = {"in_vocab": False, "neighbors": []}
                continue
            out[name] = {
                "in_vocab": self._has(name, word),
                "neighbors": [{"word": w, "similarity": round(float(s), 3)}
                              for w, s in kv.most_similar(word, topn=topn)],
            }
        return out

    def analogy(self, a: str, b: str, c: str, topn: int = 5) -> Dict[str, Dict]:
        """a − b + c, e.g. king − man + woman."""
        a, b, c = (self._norm(w) for w in (a, b, c))
        out = {}
        for name, kv in self.models.items():
            missing = [w for w in (a, b, c) if not self._can_embed(name, w)]
            if missing:
                out[name] = {"missing": missing, "answers": []}
                continue
            res = kv.most_similar(positive=[a, c], negative=[b], topn=topn)
            out[name] = {"missing": [], "answers": [{"word": w, "similarity": round(float(s), 3)}
                                                     for w, s in res]}
        return out

    def similarity(self, w1: str, w2: str) -> Dict[str, Optional[float]]:
        w1, w2 = self._norm(w1), self._norm(w2)
        return {
            name: (round(float(kv.similarity(w1, w2)), 3)
                   if self._can_embed(name, w1) and self._can_embed(name, w2) else None)
            for name, kv in self.models.items()
        }

    def project(self, words: List[str]) -> Dict[str, Dict]:
        """2-D PCA of the given words, fitted separately per model."""
        words = [self._norm(w) for w in words if w.strip()]
        out = {}
        for name, kv in self.models.items():
            kept = [w for w in words if self._can_embed(name, w)]
            if len(kept) < 2:
                out[name] = {"points": [], "missing": [w for w in words if w not in kept]}
                continue
            X = np.array([kv[w] for w in kept], dtype=np.float64)
            X -= X.mean(axis=0)
            _, _, vt = np.linalg.svd(X, full_matrices=False)
            xy = X @ vt[:2].T
            out[name] = {
                "points": [{"word": w, "x": round(float(p[0]), 4), "y": round(float(p[1]), 4)}
                           for w, p in zip(kept, xy)],
                "missing": [w for w in words if w not in kept],
            }
        return out
