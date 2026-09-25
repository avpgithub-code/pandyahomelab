"""The 22 handcrafted question-pair features from L8, grouped as the lecture does.

All features are computed on preprocessed questions. SAFE_DIV keeps the ratios
defined when a question is empty or all stopwords (the lecture's 0.0001).

Two library swaps from the notebook, same definitions:
- fuzzywuzzy -> rapidfuzz (its maintained, MIT-licensed successor)
- distance.lcsubstrings -> difflib.SequenceMatcher.find_longest_match
"""
from difflib import SequenceMatcher
from typing import Dict, List

import numpy as np
from rapidfuzz import fuzz

SAFE_DIV = 0.0001

FEATURE_GROUPS: Dict[str, List[str]] = {
    "basic": [
        "q1_len", "q2_len", "q1_num_words", "q2_num_words",
        "word_common", "word_total", "word_share",
    ],
    "token": [
        "cwc_min", "cwc_max", "csc_min", "csc_max",
        "ctc_min", "ctc_max", "last_word_eq", "first_word_eq",
    ],
    "length": ["abs_len_diff", "mean_len", "longest_substr_ratio"],
    "fuzzy": ["fuzz_ratio", "fuzz_partial_ratio", "token_sort_ratio", "token_set_ratio"],
}
FEATURE_NAMES: List[str] = [name for group in FEATURE_GROUPS.values() for name in group]


def _stopwords() -> frozenset:
    """NLTK's English list, as in the lecture. The Docker image downloads the
    corpus at build time; there's no runtime network fallback on purpose."""
    from nltk.corpus import stopwords

    return frozenset(stopwords.words("english"))


class PairFeatureBuilder:
    """Maps (q1, q2) preprocessed strings to the 22-value feature vector."""

    def __init__(self, stopwords: frozenset = None):
        self._stops = stopwords if stopwords is not None else _stopwords()

    def build(self, q1: str, q2: str) -> Dict[str, float]:
        return {**_basic(q1, q2), **self._token(q1, q2), **_length(q1, q2), **_fuzzy(q1, q2)}

    def build_matrix(self, q1s: List[str], q2s: List[str]) -> np.ndarray:
        rows = [self.build(a, b) for a, b in zip(q1s, q2s)]
        return np.array([[r[name] for name in FEATURE_NAMES] for r in rows], dtype=np.float32)

    def _token(self, q1: str, q2: str) -> Dict[str, float]:
        t1, t2 = q1.split(), q2.split()
        if not t1 or not t2:
            return {name: 0.0 for name in FEATURE_GROUPS["token"]}
        w1 = {w for w in t1 if w not in self._stops}
        w2 = {w for w in t2 if w not in self._stops}
        s1 = {w for w in t1 if w in self._stops}
        s2 = {w for w in t2 if w in self._stops}
        common_words = len(w1 & w2)
        common_stops = len(s1 & s2)
        common_tokens = len(set(t1) & set(t2))
        return {
            "cwc_min": common_words / (min(len(w1), len(w2)) + SAFE_DIV),
            "cwc_max": common_words / (max(len(w1), len(w2)) + SAFE_DIV),
            "csc_min": common_stops / (min(len(s1), len(s2)) + SAFE_DIV),
            "csc_max": common_stops / (max(len(s1), len(s2)) + SAFE_DIV),
            "ctc_min": common_tokens / (min(len(t1), len(t2)) + SAFE_DIV),
            "ctc_max": common_tokens / (max(len(t1), len(t2)) + SAFE_DIV),
            "last_word_eq": float(t1[-1] == t2[-1]),
            "first_word_eq": float(t1[0] == t2[0]),
        }


def _basic(q1: str, q2: str) -> Dict[str, float]:
    w1, w2 = set(q1.split()), set(q2.split())
    common, total = len(w1 & w2), len(w1) + len(w2)
    return {
        "q1_len": float(len(q1)),
        "q2_len": float(len(q2)),
        "q1_num_words": float(len(q1.split())),
        "q2_num_words": float(len(q2.split())),
        "word_common": float(common),
        "word_total": float(total),
        "word_share": round(common / total, 2) if total else 0.0,
    }


def _length(q1: str, q2: str) -> Dict[str, float]:
    t1, t2 = q1.split(), q2.split()
    if not t1 or not t2:
        return {name: 0.0 for name in FEATURE_GROUPS["length"]}
    match = SequenceMatcher(None, q1, q2, autojunk=False).find_longest_match(0, len(q1), 0, len(q2))
    return {
        "abs_len_diff": float(abs(len(t1) - len(t2))),
        "mean_len": (len(t1) + len(t2)) / 2,
        "longest_substr_ratio": match.size / (min(len(q1), len(q2)) + 1),
    }


def _fuzzy(q1: str, q2: str) -> Dict[str, float]:
    return {
        "fuzz_ratio": float(round(fuzz.ratio(q1, q2))),
        "fuzz_partial_ratio": float(round(fuzz.partial_ratio(q1, q2))),
        "token_sort_ratio": float(round(fuzz.token_sort_ratio(q1, q2))),
        "token_set_ratio": float(round(fuzz.token_set_ratio(q1, q2))),
    }
