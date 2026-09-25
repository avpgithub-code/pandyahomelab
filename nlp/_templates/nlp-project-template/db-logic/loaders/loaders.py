"""Dataset loading and splitting.

The template ships a tiny built-in corpus so the service, tests and About drawer
work end-to-end before the real dataset exists. Replace SAMPLE_CORPUS with the
demo's dataset (raw data stays out of git — /data/ is gitignored; check the
licence before baking a dataset into the image).
"""
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from sklearn.model_selection import train_test_split

SAMPLE_CORPUS = [
    ("I loved this film, the acting was superb", "positive"),
    ("What a wonderful and moving story", "positive"),
    ("Brilliant plot and a great soundtrack", "positive"),
    ("The best meal I have had in years", "positive"),
    ("Friendly staff and excellent service", "positive"),
    ("An absolute joy from start to finish", "positive"),
    ("Great value, would happily buy again", "positive"),
    ("Clever, funny and beautifully shot", "positive"),
    ("I really enjoyed every chapter of this book", "positive"),
    ("Fantastic experience, highly recommended", "positive"),
    ("The product works perfectly and arrived early", "positive"),
    ("A delightful surprise, better than expected", "positive"),
    ("I hated this film, the acting was wooden", "negative"),
    ("What a boring and predictable story", "negative"),
    ("Terrible plot and an annoying soundtrack", "negative"),
    ("The worst meal I have had in years", "negative"),
    ("Rude staff and awful service", "negative"),
    ("An absolute chore from start to finish", "negative"),
    ("Poor value, would never buy again", "negative"),
    ("Dull, slow and badly shot", "negative"),
    ("I could not finish this book, it was tedious", "negative"),
    ("Horrible experience, avoid at all costs", "negative"),
    ("The product broke after one day and arrived late", "negative"),
    ("A disappointing mess, worse than expected", "negative"),
]


@dataclass
class Split:
    train: pd.DataFrame
    test: pd.DataFrame


class TextLoader:
    """Loads a (text, label) frame from CSV, or the built-in sample corpus."""

    def __init__(self, data_path: Optional[str] = None):
        self._data_path = data_path

    def load(self) -> pd.DataFrame:
        if self._data_path:
            df = pd.read_csv(self._data_path)
        else:
            df = pd.DataFrame(SAMPLE_CORPUS, columns=["text", "label"])
        return df[["text", "label"]].dropna().reset_index(drop=True)

    def train_test_split(
        self,
        test_size: float = 0.25,
        seed: int = 42,
        df: Optional[pd.DataFrame] = None,
    ) -> Split:
        df = df if df is not None else self.load()
        train, test = train_test_split(
            df, test_size=test_size, random_state=seed, stratify=df["label"]
        )
        return Split(train=train.reset_index(drop=True), test=test.reset_index(drop=True))
