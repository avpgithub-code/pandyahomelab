"""Tests for sliding-window construction + WindowScaler."""
import numpy as np
import pytest

from db_logic.transforms.preprocessor import WindowScaler, make_windows


def test_make_windows_basic_shapes():
    series = np.arange(20, dtype=np.float32)
    X, y = make_windows(series, window_size=5, horizon=1)
    # n_samples = len(series) - window_size - horizon + 1 = 20 - 5 - 1 + 1 = 15
    assert X.shape == (15, 5)
    assert y.shape == (15, 1)
    np.testing.assert_array_equal(X[0], [0, 1, 2, 3, 4])
    np.testing.assert_array_equal(y[0], [5])
    np.testing.assert_array_equal(X[-1], [14, 15, 16, 17, 18])
    np.testing.assert_array_equal(y[-1], [19])


def test_make_windows_multi_step_horizon():
    series = np.arange(20, dtype=np.float32)
    X, y = make_windows(series, window_size=5, horizon=3)
    assert X.shape == (13, 5)
    assert y.shape == (13, 3)
    np.testing.assert_array_equal(y[0], [5, 6, 7])
    np.testing.assert_array_equal(y[-1], [17, 18, 19])


def test_make_windows_rejects_too_short_series():
    with pytest.raises(ValueError, match="too short"):
        make_windows(np.arange(5, dtype=np.float32), window_size=5, horizon=1)


def test_make_windows_rejects_invalid_args():
    series = np.arange(20, dtype=np.float32)
    with pytest.raises(ValueError, match="window_size"):
        make_windows(series, window_size=0, horizon=1)
    with pytest.raises(ValueError, match="horizon"):
        make_windows(series, window_size=5, horizon=0)


def test_window_scaler_roundtrip():
    rng = np.random.default_rng(0)
    train = rng.normal(loc=10_000, scale=2000, size=300).astype(np.float32)
    val = rng.normal(loc=10_000, scale=2000, size=50).astype(np.float32)

    scaler = WindowScaler().fit(train)
    scaled_train = scaler.transform(train)
    assert scaled_train.mean() == pytest.approx(0.0, abs=1e-4)
    assert scaled_train.std() == pytest.approx(1.0, abs=1e-2)

    # Val transformed using train statistics is NOT zero-mean — that's expected.
    scaled_val = scaler.transform(val)
    assert scaled_val.shape == val.shape

    # Round-trip restores values to original scale.
    np.testing.assert_allclose(scaler.inverse_transform(scaled_train), train, rtol=1e-5)
    np.testing.assert_allclose(scaler.inverse_transform(scaled_val), val, rtol=1e-5)


def test_window_scaler_rejects_unfitted_use():
    scaler = WindowScaler()
    with pytest.raises(RuntimeError, match="not fitted"):
        scaler.transform(np.arange(10, dtype=np.float32))
    with pytest.raises(RuntimeError, match="not fitted"):
        scaler.inverse_transform(np.arange(10, dtype=np.float32))


def test_window_scaler_fit_transform_equivalent():
    series = np.arange(50, dtype=np.float32)
    a = WindowScaler().fit_transform(series)
    b = WindowScaler().fit(series).transform(series)
    np.testing.assert_allclose(a, b)
