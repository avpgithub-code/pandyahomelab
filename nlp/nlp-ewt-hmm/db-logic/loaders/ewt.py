"""Universal Dependencies English Web Treebank (UD_English-EWT), release r2.16.

254k words of blogs, newsgroups, emails, reviews and Q&A posts, each hand-tagged
with a Universal POS tag. Licensed CC BY-SA 4.0 (credit in the About drawer).
Publishable, but it is still fetched by `make data` into data/ewt/ (gitignored,
dockerignored) and mounted read-only, the same as every Phase 3 dataset.
The official train/test split is used as-is.
"""
import os
from typing import Dict, List, Tuple

from db_logic.transforms.tagset import to_universal12

EWT_REPO = "UniversalDependencies/UD_English-EWT"
EWT_RELEASE = "r2.16"
# Commit behind the r2.16 tag, so a moved tag can't change the data.
EWT_COMMIT = "4c89b5833a70aa5ed3a00bad2f23f57992cc7df8"

# split -> (repo path, sha256)
EWT_FILES: Dict[str, Tuple[str, str]] = {
    "train": (
        "en_ewt-ud-train.conllu",
        "3fb78e2b55482c8ee00caa653af436c88c9e5bc9a73ce26e4ae3ddc79d2b7e7b",
    ),
    "test": (
        "en_ewt-ud-test.conllu",
        "e266e515a0a7547657ed3d90d9ba46487d6bd251f27ad4269d4e8a427c8555cd",
    ),
}

Sentence = List[Tuple[str, str]]


def ewt_url(split: str) -> str:
    path, _ = EWT_FILES[split]
    return f"https://raw.githubusercontent.com/{EWT_REPO}/{EWT_COMMIT}/{path}"


def ewt_local_path(data_dir: str, split: str) -> str:
    return os.path.join(data_dir, EWT_FILES[split][0])


def read_conllu(path: str, universal12: bool = True) -> List[Sentence]:
    """(word, tag) sentences from a CoNLL-U file.

    Multi-word token ranges ("don't" = 3-4) and empty nodes (8.1) are skipped;
    the syntactic words under them are kept, which is what UPOS tags.
    """
    sents: List[Sentence] = []
    cur: Sentence = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                if cur:
                    sents.append(cur)
                cur = []
                continue
            if line.startswith("#"):
                continue
            cols = line.split("\t")
            if "-" in cols[0] or "." in cols[0]:
                continue
            cur.append((cols[1], to_universal12(cols[3]) if universal12 else cols[3]))
    if cur:
        sents.append(cur)
    return sents


class EwtLoader:
    """Loads EWT splits from data_dir as (word, Universal-12 tag) sentences."""

    def __init__(self, data_dir: str):
        self._data_dir = data_dir

    def load(self, split: str, universal12: bool = True) -> List[Sentence]:
        path = ewt_local_path(self._data_dir, split)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"{path} not found. Run `make data` (scripts/fetch_ewt.py) first."
            )
        return read_conllu(path, universal12)
