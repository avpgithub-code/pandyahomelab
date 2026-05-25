"""Loader for the NYC CitiBike daily ride counts CSV.

The CSV is produced by db-logic/scripts/build_dataset.py (run once locally,
result committed to db-logic/data/bike_share_daily.csv) and baked into the
Docker image at build time. At runtime this loader reads the committed CSV
and exposes the helpers the application layer needs: full series, time-
respecting train/val/test split, and trailing-window lookups for inference.
"""
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd

DEFAULT_DATA_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "bike_share_daily.csv")
)


@dataclass(frozen=True)
class Split:
    """Time-respecting train/val/test split of a daily-counts DataFrame.

    All three frames have the same `date`-indexed shape (DatetimeIndex, single
    `trips` column) and are temporally non-overlapping in that order.
    """
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame


class BikeShareLoader:
    """Reads the committed daily-counts CSV and serves it to upstream layers.

    v1.0.0 uses only the `date` and `trips` columns. The toddwschneider source
    ships with bonus weather/holiday/weekday columns that are loaded but
    dropped here; future polish (Phase 2b.x) could promote them into a
    multivariate LSTM without changing this loader's public surface.
    """

    DATE_COL = "date"
    TARGET_COL = "trips"

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or DEFAULT_DATA_PATH
        self._df: Optional[pd.DataFrame] = None

    def load_daily_counts(self) -> pd.DataFrame:
        """Returns a DataFrame indexed by date with a single `trips` int column.

        Cached on the instance — repeated calls return the same DataFrame.
        """
        if self._df is None:
            raw = pd.read_csv(self.data_path, parse_dates=[self.DATE_COL])
            df = raw[[self.DATE_COL, self.TARGET_COL]].copy()
            df = df.set_index(self.DATE_COL).sort_index()
            df[self.TARGET_COL] = df[self.TARGET_COL].astype(int)
            self._df = df
        return self._df

    def train_val_test_split(
        self,
        val_days: int = 90,
        test_days: int = 180,
        df: Optional[pd.DataFrame] = None,
    ) -> Split:
        """Splits the series in temporal order — train | val | test.

        The test set is the most recent `test_days` rows, val is the
        `val_days` rows immediately before that, and train is everything
        before val. No shuffling; no leakage across boundaries.
        """
        if df is None:
            df = self.load_daily_counts()
        n = len(df)
        if val_days + test_days >= n:
            raise ValueError(
                f"val_days ({val_days}) + test_days ({test_days}) must be < "
                f"len(series) ({n})"
            )
        test = df.iloc[-test_days:]
        val = df.iloc[-(val_days + test_days):-test_days]
        train = df.iloc[: -(val_days + test_days)]
        return Split(train=train, val=val, test=test)

    def get_window_at(
        self,
        anchor_date,
        window_size: int,
        df: Optional[pd.DataFrame] = None,
    ) -> Tuple[pd.Timestamp, np.ndarray]:
        """Returns the `window_size` daily counts ending at (and including) anchor_date.

        Used at inference time: given a visitor-picked anchor date, we feed the
        trailing N days into the LSTM as the starting context for the
        autoregressive forecast.

        Returns (resolved_anchor_timestamp, np.ndarray of shape (window_size,)).
        Raises if anchor_date is outside the loaded series, or if fewer than
        window_size days precede it.
        """
        if df is None:
            df = self.load_daily_counts()
        anchor = pd.Timestamp(anchor_date).normalize()
        if anchor < df.index.min() or anchor > df.index.max():
            raise ValueError(
                f"anchor {anchor.date()} outside loaded range "
                f"[{df.index.min().date()}, {df.index.max().date()}]"
            )
        idx_pos = df.index.searchsorted(anchor, side="right") - 1
        if idx_pos + 1 < window_size:
            raise ValueError(
                f"only {idx_pos + 1} days available before anchor {anchor.date()}; "
                f"need {window_size}"
            )
        window = df[self.TARGET_COL].iloc[idx_pos + 1 - window_size: idx_pos + 1].to_numpy()
        return df.index[idx_pos], window.astype(np.float32)

    def get_last_window(self, window_size: int) -> np.ndarray:
        """Trailing `window_size` days ending at the most recent observation."""
        df = self.load_daily_counts()
        _, window = self.get_window_at(df.index.max(), window_size, df=df)
        return window
