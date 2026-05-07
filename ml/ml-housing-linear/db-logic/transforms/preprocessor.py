import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


class DataPreprocessor:
    """Normalizes features using StandardScaler (zero mean, unit variance)."""

    def __init__(self):
        self._scaler = StandardScaler()
        self._fitted = False

    def fit(self, X: pd.DataFrame) -> "DataPreprocessor":
        self._scaler.fit(X)
        self._fitted = True
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Preprocessor must be fitted before calling transform.")
        return self._scaler.transform(X)

    def fit_transform(self, X: pd.DataFrame) -> np.ndarray:
        return self.fit(X).transform(X)

    @property
    def is_fitted(self) -> bool:
        return self._fitted
