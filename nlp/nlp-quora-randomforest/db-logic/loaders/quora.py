"""Quora Question Pairs, via the GLUE QQP task (nyu-mll/glue on Hugging Face).

GLUE's QQP test split has no labels, so the demo uses GLUE train for training and
GLUE validation as its held-out test set. Both are the 2017 Quora release, which
is licensed for non-commercial use only: the parquet files live under data/qqp/
(gitignored, dockerignored) and are mounted at runtime, never baked into the image.
Fetch them with `make data`.

Columns are renamed to the Kaggle / lecture names (question1, question2,
is_duplicate) so the L8 feature code reads the same as the course notebook.
"""
import os
from dataclasses import dataclass
from typing import Optional

import pandas as pd

# Pinned revision so every retrain sees byte-identical data.
GLUE_REPO = "nyu-mll/glue"
GLUE_REVISION = "bcdcba79d07bc864c1c254ccfcedcce55bcc9a8c"

# split -> (repo path, sha256). The test split is left out: its labels are hidden.
QQP_FILES = {
    "train": (
        "qqp/train-00000-of-00001.parquet",
        "4d6f02e643f7c36e9a4f7d4971a5ee9bd74063a319452fe6c87850c739774cd7",
    ),
    "validation": (
        "qqp/validation-00000-of-00001.parquet",
        "efd86a539c412d74874ee451573d7bd142f56c47fe36de033b9f367d8bb0fa71",
    ),
}

COLUMNS = ["question1", "question2", "is_duplicate"]


def qqp_url(split: str) -> str:
    path, _ = QQP_FILES[split]
    return f"https://huggingface.co/datasets/{GLUE_REPO}/resolve/{GLUE_REVISION}/{path}"


def qqp_local_path(data_dir: str, split: str) -> str:
    return os.path.join(data_dir, f"{split}.parquet")


@dataclass
class PairSplit:
    train: pd.DataFrame
    test: pd.DataFrame


class QuoraPairLoader:
    """Loads GLUE QQP parquet files from data_dir as (question1, question2, is_duplicate)."""

    def __init__(self, data_dir: str):
        self._data_dir = data_dir

    def load(self, split: str) -> pd.DataFrame:
        path = qqp_local_path(self._data_dir, split)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"{path} not found. Run `make data` (scripts/fetch_qqp.py) first."
            )
        df = pd.read_parquet(path, columns=["question1", "question2", "label"])
        df = df.rename(columns={"label": "is_duplicate"})
        df = df.dropna()
        # A handful of GLUE rows have an empty question; they carry no signal.
        blank = (df["question1"].str.strip() == "") | (df["question2"].str.strip() == "")
        return df[~blank][COLUMNS].reset_index(drop=True)

    def train_test_split(
        self,
        max_train_rows: Optional[int] = None,
        max_test_rows: Optional[int] = None,
        seed: int = 42,
    ) -> PairSplit:
        """GLUE train -> train, GLUE validation -> test, each optionally subsampled.

        Subsampling is stratified on is_duplicate so the ~37% duplicate rate holds
        at any size; that is what keeps a 100k-row run inside the memory guardrail
        comparable with a full 364k-row run.
        """
        return PairSplit(
            train=_stratified_sample(self.load("train"), max_train_rows, seed),
            test=_stratified_sample(self.load("validation"), max_test_rows, seed),
        )


def _stratified_sample(df: pd.DataFrame, n: Optional[int], seed: int) -> pd.DataFrame:
    if n is None or n >= len(df):
        return df
    frac = n / len(df)
    sampled = df.groupby("is_duplicate", group_keys=False).apply(
        lambda g: g.sample(frac=frac, random_state=seed)
    )
    return sampled.sample(frac=1.0, random_state=seed).reset_index(drop=True)
