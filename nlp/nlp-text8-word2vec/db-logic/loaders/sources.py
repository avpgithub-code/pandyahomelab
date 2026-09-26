"""Pinned sources for the corpus and the reference vectors, and where they land.

Everything lives under data/ (gitignored, dockerignored) and is mounted into the
container read-only:
  data/raw/     text8 (Wikipedia, CC BY-SA) and GloVe 6B 100d (PDDL), as downloaded
  data/models/  the trained and trimmed KeyedVectors + metrics.json (scripts/train_embeddings.py)
"""
import os

# text8: the first 10^8 bytes of a cleaned English Wikipedia dump (Matt Mahoney).
TEXT8 = {
    "url": "https://mattmahoney.net/dc/text8.zip",
    "sha256": "a6640522afe85d1963ad56c05b0ede0a0c000dddc9671758a6cc09b7a38e5232",
    "file": "text8.zip",
}

# GloVe 6B 100d (Wikipedia 2014 + Gigaword 5), gensim KeyedVectors, pinned revision.
GLOVE_REPO = "fse/glove-wiki-gigaword-100"
GLOVE_REVISION = "3282d5e7c5e979c2411ba9703d63a46243a2047e"
GLOVE_FILES = {
    "glove-wiki-gigaword-100.model":
        "e21d1bd8eb25e315b64308187a44f813d6b59bbfbe9633ad6cd504753c20d791",
    "glove-wiki-gigaword-100.model.vectors.npy":
        "58620c9e3f3f70214133cdc5899b9553443198a27d320c34a1b39341e1908c67",
}


def glove_url(name: str) -> str:
    return f"https://huggingface.co/{GLOVE_REPO}/resolve/{GLOVE_REVISION}/{name}"


def raw_dir(data_dir: str) -> str:
    return os.path.join(data_dir, "raw")


def models_dir(data_dir: str) -> str:
    return os.path.join(data_dir, "models")
