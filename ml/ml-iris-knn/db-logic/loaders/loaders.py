"""Data loaders for the Iris KNN classifier."""
import os
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import pandas as pd
from sklearn.model_selection import train_test_split


class BaseDataLoader(ABC):
    @abstractmethod
    def load(self) -> pd.DataFrame:
        pass


class LocalDataLoader(BaseDataLoader):
    """Load Iris dataset from a local CSV file."""

    FEATURE_COLS = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
    TARGET_COL = "species"
    LABEL_MAP = {"setosa": 0, "versicolor": 1, "virginica": 2}

    def __init__(self, path: Optional[str] = None):
        if path is None:
            path = os.path.join(os.path.dirname(__file__), "../../data/iris.csv")
        self.path = os.path.abspath(path)

    def load(self) -> pd.DataFrame:
        df = pd.read_csv(self.path)
        df[self.TARGET_COL] = df[self.TARGET_COL].map(self.LABEL_MAP)
        return df

    def get_features(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[self.FEATURE_COLS]

    def get_target(self, df: pd.DataFrame) -> pd.Series:
        return df[self.TARGET_COL]

    def get_feature_names(self) -> List[str]:
        return self.FEATURE_COLS

    def split(
        self, df: pd.DataFrame, test_size: float = 0.2, random_state: int = 42
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        X = self.get_features(df)
        y = self.get_target(df)
        return train_test_split(X, y, test_size=test_size, random_state=random_state)
