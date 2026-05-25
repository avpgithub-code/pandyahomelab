"""Windowing + scaling helpers for the LSTM time-series pipeline.

The LSTM consumes (batch, window_size, 1) tensors and predicts the next
day's count. `make_windows` produces these from a 1-D series; `WindowScaler`
standardises values to zero-mean / unit-variance using train-set statistics
and exposes `inverse_transform` so the application layer can convert
model-space forecasts back to ride counts for the UI.
"""
from dataclasses import dataclass
from typing import Tuple

import numpy as np
from sklearn.preprocessing import StandardScaler


def make_windows(
    series: np.ndarray,
    window_size: int,
    horizon: int = 1,
) -> Tuple[np.ndarray, np.ndarray]:
    """Convert a 1-D series into sliding (X, y) windows for supervised training.

    For a series [s0, s1, ..., s_{n-1}], with window_size=W and horizon=h:
      X[i] = series[i : i+W]            shape (W,)
      y[i] = series[i+W : i+W+h]        shape (h,)

    Returns:
      X: float32 array of shape (n_samples, window_size)
      y: float32 array of shape (n_samples, horizon)

    Raises if the series is too short to produce at least one window.
    """
    if window_size < 1:
        raise ValueError(f"window_size must be ≥ 1, got {window_size}")
    if horizon < 1:
        raise ValueError(f"horizon must be ≥ 1, got {horizon}")
    series = np.asarray(series, dtype=np.float32)
    n_samples = len(series) - window_size - horizon + 1
    if n_samples < 1:
        raise ValueError(
            f"series of length {len(series)} too short for "
            f"window_size={window_size}, horizon={horizon}"
        )
    X = np.lib.stride_tricks.sliding_window_view(series, window_size)[:n_samples]
    y = np.stack([series[i + window_size: i + window_size + horizon] for i in range(n_samples)])
    return X.astype(np.float32, copy=True), y.astype(np.float32, copy=True)


@dataclass
class WindowScaler:
    """Standardise daily counts to model space and back.

    Wraps `sklearn.preprocessing.StandardScaler`. Fit ONLY on the training
    series — applying it to val/test/inference data afterwards is what
    keeps the evaluation honest. Same instance is used at inference, so
    persist it alongside the model checkpoint.
    """

    scaler: StandardScaler = None
    _fitted: bool = False

    def fit(self, series: np.ndarray) -> "WindowScaler":
        self.scaler = StandardScaler()
        self.scaler.fit(np.asarray(series, dtype=np.float32).reshape(-1, 1))
        self._fitted = True
        return self

    def transform(self, series: np.ndarray) -> np.ndarray:
        self._require_fitted()
        a = np.asarray(series, dtype=np.float32)
        flat = self.scaler.transform(a.reshape(-1, 1)).reshape(a.shape)
        return flat.astype(np.float32)

    def fit_transform(self, series: np.ndarray) -> np.ndarray:
        return self.fit(series).transform(series)

    def inverse_transform(self, scaled: np.ndarray) -> np.ndarray:
        self._require_fitted()
        a = np.asarray(scaled, dtype=np.float32)
        flat = self.scaler.inverse_transform(a.reshape(-1, 1)).reshape(a.shape)
        return flat.astype(np.float32)

    def _require_fitted(self):
        if not self._fitted or self.scaler is None:
            raise RuntimeError("WindowScaler is not fitted; call .fit(train_series) first")
