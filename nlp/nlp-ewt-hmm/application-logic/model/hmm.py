"""Bigram hidden Markov model part-of-speech tagger, decoded with Viterbi.

Built by hand with numpy (no NLTK / hmmlearn), because counting the tables and
filling the trellis *is* the lesson (lecture 7):

  hidden states  = the 12 universal tags
  observations   = words
  start   P(t1)          counted from sentence-initial tags
  transition P(t_i | t_i-1)  counted from adjacent tag pairs, add-1 smoothed
  emission   P(w | t)        counted from (word, tag) pairs

Everything is kept in log space, so a 40-word sentence doesn't underflow to 0.

Unknown words (never seen in training) have no emission count. Three strategies:

  laplace     add-1 over the vocabulary plus one <UNK> column that no training
              word maps to, so every tag gives an unknown word the same tiny
              count; only the transitions can pick its tag.
  unk         words seen once in training (hapaxes) are rewritten to <UNK>, so
              P(<UNK> | tag) is learned from the words most like unseen ones.
  signatures  as `unk`, but hapaxes become shape classes: <UNK-ing>, <UNK-CAP-s>,
              <UNK-NUM>... so a new "-ly" word leans ADV and a capitalised one NOUN.
"""
import json
import re
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

UNKNOWN_STRATEGIES: Dict[str, str] = {
    "laplace": "Add-1 smoothing, one shared <UNK>",
    "unk": "Rare words → <UNK> (learned)",
    "signatures": "Rare words → suffix/shape classes",
}
DEFAULT_STRATEGY = "signatures"
UNK = "<UNK>"
# Emission add-k for the rare-word strategies: small, because <UNK> classes already
# carry the probability mass that unknown words need.
EMISSION_K_RARE = 1e-3
EMISSION_K_LAPLACE = 1.0
_SUFFIXES = ("ing", "ed", "ly", "tion", "ness", "ment", "able", "ous", "ive", "al",
             "est", "er", "s")
_NUMBER = re.compile(r"[\d.,:/-]+")


def signature(word: str) -> str:
    """Shape class for a rare or unseen word: number, punctuation, then suffix and case."""
    if _NUMBER.fullmatch(word) and any(c.isdigit() for c in word):
        return "<UNK-NUM>"
    if not any(c.isalnum() for c in word):
        return "<UNK-PUNCT>"
    lower = word.lower()
    cap = "-CAP" if word[0].isupper() else ""
    for suf in _SUFFIXES:
        if lower.endswith(suf) and len(lower) > len(suf) + 2:
            return f"<UNK{cap}-{suf}>"
    if "-" in word:
        return f"<UNK{cap}-HYPH>"
    return f"<UNK{cap}>"


Sentence = Sequence[Tuple[str, str]]


class HmmTagger:
    def __init__(self, unknown: str = DEFAULT_STRATEGY):
        if unknown not in UNKNOWN_STRATEGIES:
            raise ValueError(f"unknown strategy {unknown!r}")
        self.unknown = unknown
        self.tags: List[str] = []
        self.known: set = set()
        self._vocab: set = set()
        self._col: Dict[str, int] = {}
        self.log_start = self.log_trans = self.log_emit = np.zeros(0)
        self.start_counts = self.trans_counts = self.emit_counts = np.zeros(0)

    # ——— training ———
    def observation(self, word: str) -> str:
        """The emission column a word reads from: itself, or its <UNK> class."""
        if word in self._vocab:
            return word
        return signature(word) if self.unknown == "signatures" else UNK

    def fit(self, sents: Sequence[Sentence], tags: Optional[Sequence[str]] = None) -> "HmmTagger":
        counts = Counter(w for s in sents for w, _ in s)
        self.known = set(counts)
        if self.unknown == "laplace":
            self._vocab = set(counts)
        else:
            self._vocab = {w for w, c in counts.items() if c > 1}
        columns = set(self._vocab) | {UNK}
        if self.unknown == "signatures":
            columns |= {signature(w) for w in counts}
        self._col = {w: i for i, w in enumerate(sorted(columns))}

        self.tags = list(tags) if tags else sorted({t for s in sents for _, t in s})
        ti = {t: i for i, t in enumerate(self.tags)}
        T = len(self.tags)
        start, trans = np.zeros(T), np.zeros((T, T))
        emit = np.zeros((T, len(self._col)))
        for s in sents:
            prev = None
            for w, t in s:
                j = ti[t]
                emit[j, self._col[self.observation(w)]] += 1
                if prev is None:
                    start[j] += 1
                else:
                    trans[prev, j] += 1
                prev = j
        self.start_counts, self.trans_counts, self.emit_counts = start, trans, emit
        self.log_start = np.log((start + 1) / (start.sum() + T))
        self.log_trans = np.log((trans + 1) / (trans.sum(1, keepdims=True) + T))
        k = EMISSION_K_LAPLACE if self.unknown == "laplace" else EMISSION_K_RARE
        self.log_emit = np.log((emit + k) / (emit.sum(1, keepdims=True) + k * len(self._col)))
        return self

    # ——— decoding ———
    def _columns(self, words: Sequence[str]) -> List[int]:
        return [self._col.get(self.observation(w), self._col[UNK]) for w in words]

    def viterbi(self, words: Sequence[str]) -> Dict:
        """Best tag path plus the full trellis.

        trellis[i][t]  log P of the best path that ends in tag t at word i
        back[i][t]     the tag at word i-1 on that best path
        """
        if not words:
            return {"tags": [], "trellis": np.zeros((0, len(self.tags))), "back": np.zeros((0, 0), int)}
        cols = self._columns(words)
        n, T = len(words), len(self.tags)
        trellis = np.zeros((n, T))
        back = np.zeros((n, T), dtype=np.int32)
        trellis[0] = self.log_start + self.log_emit[:, cols[0]]
        for i in range(1, n):
            cand = trellis[i - 1][:, None] + self.log_trans      # previous tag x current tag
            back[i] = cand.argmax(0)
            trellis[i] = cand.max(0) + self.log_emit[:, cols[i]]
        path = [int(trellis[-1].argmax())]
        for i in range(n - 1, 0, -1):
            path.append(int(back[i, path[-1]]))
        path.reverse()
        return {"tags": [self.tags[j] for j in path], "path": path, "trellis": trellis,
                "back": back, "columns": cols}

    def tag(self, words: Sequence[str]) -> List[str]:
        return self.viterbi(words)["tags"]

    def emission_best(self, word: str) -> str:
        """The tag this word would get from emissions alone (no transitions)."""
        return self.tags[int(self.log_emit[:, self._columns([word])[0]].argmax())]

    # ——— inspection ———
    @property
    def vocabulary_size(self) -> int:
        return len(self._vocab)

    @property
    def n_columns(self) -> int:
        return len(self._col)

    def transition_matrix(self) -> List[List[float]]:
        return np.exp(self.log_trans).round(3).tolist()

    def start_probs(self) -> List[float]:
        return np.exp(self.log_start).round(3).tolist()

    def top_emissions(self, k: int = 5) -> Dict[str, List[Dict]]:
        """Most likely words per tag, skipping the <UNK> classes."""
        words = sorted(self._col, key=self._col.get)
        out = {}
        for i, t in enumerate(self.tags):
            order = np.argsort(-self.emit_counts[i])
            top = []
            for j in order:
                if words[j].startswith("<UNK"):
                    continue
                top.append({"word": words[j], "p": round(float(np.exp(self.log_emit[i, j])), 4)})
                if len(top) == k:
                    break
            out[t] = top
        return out

    def top_signatures(self, k: int = 8) -> List[Dict]:
        """The most frequent <UNK> classes and the tag each one leans to."""
        rows = []
        for w, j in self._col.items():
            if not w.startswith("<UNK"):
                continue
            col = self.emit_counts[:, j]
            if col.sum() == 0:
                continue
            share = col / col.sum()
            best = int(share.argmax())
            rows.append({"class": w, "count": int(col.sum()), "leans": self.tags[best],
                         "share": f"{share[best] * 100:.0f}%"})
        return sorted(rows, key=lambda r: -r["count"])[:k]

    def save(self, path: str) -> None:
        np.savez_compressed(
            path, log_start=self.log_start, log_trans=self.log_trans, log_emit=self.log_emit,
            meta=np.array(json.dumps({
                "unknown": self.unknown, "tags": self.tags,
                "columns": sorted(self._col, key=self._col.get),
            })),
        )
