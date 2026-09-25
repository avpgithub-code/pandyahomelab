"""Large Movie Review Dataset (IMDB), via stanfordnlp/imdb on Hugging Face.

25,000 labelled reviews for training and 25,000 for testing, each split exactly
half positive, half negative (Maas et al., ACL 2011). The dataset card states no
licence, so it is treated like 3a's QQP: the parquet files live under data/imdb/
(gitignored, dockerignored) and are mounted at runtime, never baked into the image.
Fetch them with `make data`.
"""
import os
from dataclasses import dataclass
from typing import Optional

import pandas as pd

# Pinned revision so every retrain sees byte-identical data.
IMDB_REPO = "stanfordnlp/imdb"
IMDB_REVISION = "e6281661ce1c48d982bc483cf8a173c1bbeb5d31"

# split -> (repo path, sha256). The unlabelled "unsupervised" split is left out.
IMDB_FILES = {
    "train": (
        "plain_text/train-00000-of-00001.parquet",
        "db47d16b5c297cc0dd625e519c81319c24c9149e70e8496de5475f6fa928342c",
    ),
    "test": (
        "plain_text/test-00000-of-00001.parquet",
        "b52e26e2f872d282ffac460bf9770b25ac6f102cda0e6ca7158df98c94e8b3da",
    ),
}

COLUMNS = ["text", "label"]
LABELS = ["Negative", "Positive"]


def imdb_url(split: str) -> str:
    path, _ = IMDB_FILES[split]
    return f"https://huggingface.co/datasets/{IMDB_REPO}/resolve/{IMDB_REVISION}/{path}"


def imdb_local_path(data_dir: str, split: str) -> str:
    return os.path.join(data_dir, f"{split}.parquet")


@dataclass
class Split:
    train: pd.DataFrame
    test: pd.DataFrame


class ImdbLoader:
    """Loads IMDB parquet files from data_dir as (text, label), label 0 = negative, 1 = positive."""

    def __init__(self, data_dir: str):
        self._data_dir = data_dir

    def load(self, split: str) -> pd.DataFrame:
        path = imdb_local_path(self._data_dir, split)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"{path} not found. Run `make data` (scripts/fetch_imdb.py) first."
            )
        df = pd.read_parquet(path, columns=COLUMNS).dropna()
        return df[df["text"].str.strip() != ""].reset_index(drop=True)

    def train_test_split(
        self,
        max_train_rows: Optional[int] = None,
        max_test_rows: Optional[int] = None,
        seed: int = 42,
    ) -> Split:
        """IMDB train -> train, IMDB test -> test, each optionally subsampled (stratified)."""
        return Split(
            train=_stratified_sample(self.load("train"), max_train_rows, seed),
            test=_stratified_sample(self.load("test"), max_test_rows, seed),
        )


def _stratified_sample(df: pd.DataFrame, n: Optional[int], seed: int) -> pd.DataFrame:
    if n is None or n >= len(df):
        return df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    frac = n / len(df)
    sampled = df.groupby("label", group_keys=False).apply(
        lambda g: g.sample(frac=frac, random_state=seed)
    )
    return sampled.sample(frac=1.0, random_state=seed).reset_index(drop=True)
