"""Tests for BikeShareLoader.

All tests use a synthetic in-memory CSV fixture; the suite has no
dependency on the real bike_share_daily.csv being present.
"""
import os
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from db_logic.loaders.loaders import BikeShareLoader, Split


@pytest.fixture
def synthetic_csv(tmp_path: Path) -> str:
    """200-day synthetic series with a weekly cycle + linear trend.

    Avoids touching the committed real CSV so tests stay deterministic
    and fast (and don't break if the real file is regenerated).
    """
    n = 200
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    # Weekly cycle (peak on Saturdays) + linear growth + small noise.
    trips = 10_000 + 1500 * np.sin(2 * np.pi * np.arange(n) / 7) + 20 * np.arange(n)
    df = pd.DataFrame({"date": dates, "trips": trips.astype(int)})
    path = tmp_path / "synth_bike.csv"
    df.to_csv(path, index=False)
    return str(path)


def test_load_daily_counts_returns_indexed_frame(synthetic_csv):
    loader = BikeShareLoader(data_path=synthetic_csv)
    df = loader.load_daily_counts()
    assert isinstance(df.index, pd.DatetimeIndex)
    assert list(df.columns) == ["trips"]
    assert len(df) == 200
    assert df["trips"].dtype.kind == "i"


def test_load_daily_counts_is_cached(synthetic_csv):
    loader = BikeShareLoader(data_path=synthetic_csv)
    a = loader.load_daily_counts()
    b = loader.load_daily_counts()
    assert a is b


def test_train_val_test_split_sizes_and_ordering(synthetic_csv):
    loader = BikeShareLoader(data_path=synthetic_csv)
    split = loader.train_val_test_split(val_days=30, test_days=40)
    assert isinstance(split, Split)
    assert len(split.train) == 200 - 30 - 40
    assert len(split.val) == 30
    assert len(split.test) == 40
    assert split.train.index.max() < split.val.index.min()
    assert split.val.index.max() < split.test.index.min()


def test_split_rejects_overshoot(synthetic_csv):
    loader = BikeShareLoader(data_path=synthetic_csv)
    with pytest.raises(ValueError, match="must be < len"):
        loader.train_val_test_split(val_days=100, test_days=150)


def test_get_window_at_returns_trailing_window(synthetic_csv):
    loader = BikeShareLoader(data_path=synthetic_csv)
    anchor, window = loader.get_window_at("2020-02-15", window_size=10)
    assert anchor == pd.Timestamp("2020-02-15")
    assert window.shape == (10,)
    assert window.dtype == np.float32
    # Last value of the window equals the trips on the anchor date.
    df = loader.load_daily_counts()
    assert window[-1] == pytest.approx(df.loc["2020-02-15", "trips"])


def test_get_window_at_rejects_anchor_outside_range(synthetic_csv):
    loader = BikeShareLoader(data_path=synthetic_csv)
    with pytest.raises(ValueError, match="outside loaded range"):
        loader.get_window_at("2019-01-01", window_size=10)


def test_get_window_at_rejects_insufficient_history(synthetic_csv):
    loader = BikeShareLoader(data_path=synthetic_csv)
    # Only 5 days exist before 2020-01-05; window_size=10 must fail.
    with pytest.raises(ValueError, match="only .* days available"):
        loader.get_window_at("2020-01-05", window_size=10)


def test_get_last_window_aligns_with_series_tail(synthetic_csv):
    loader = BikeShareLoader(data_path=synthetic_csv)
    window = loader.get_last_window(window_size=14)
    df = loader.load_daily_counts()
    np.testing.assert_allclose(window, df["trips"].iloc[-14:].to_numpy().astype(np.float32))
