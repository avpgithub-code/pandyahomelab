"""LSTM time-series forecaster — PyTorch model + train/forecast wrapper.

Architecture: 1-layer LSTM, hidden_size=64, dropout=0.2, predicts the next
day's scaled ride count from a sliding window of past 28 days. The 14-day
forecast is produced at inference by autoregressive rollout (feed the
prediction for day t+1 back as input for day t+2, and so on).

Dropout stays active at inference for Monte Carlo Dropout: N=30 stochastic
forward passes per autoregressive step yield a per-step mean ± 2σ, which
the UI renders as a widening confidence band.
"""
from typing import Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

# Module-level hyperparameters surfaced so PredictionService logs the same
# values to MLflow without re-defining them. Production values come from
# configs/training.yaml; these are the fallbacks if the config is missing.
HIDDEN_SIZE = 64
NUM_LAYERS = 1
DROPOUT = 0.2
LEARNING_RATE = 1e-3
DEFAULT_EPOCHS = 50
DEFAULT_PATIENCE = 5
DEFAULT_BATCH_SIZE = 32
ARCHITECTURE = (
    f"LSTM(input_size=1, hidden_size={HIDDEN_SIZE}, num_layers={NUM_LAYERS}, "
    f"dropout={DROPOUT}) + Linear(hidden→1)"
)


class LSTMForecaster(nn.Module):
    """1-layer LSTM regressor for next-day daily ride counts."""

    def __init__(
        self,
        hidden_size: int = HIDDEN_SIZE,
        num_layers: int = NUM_LAYERS,
        dropout: float = DROPOUT,
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        # dropout in nn.LSTM only applies between stacked layers, so with
        # num_layers=1 it's a no-op. Add an explicit dropout on the LSTM
        # output instead — this is what MC Dropout will keep active at
        # inference.
        self.lstm = nn.LSTM(
            input_size=1,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (batch, seq_len, 1)
        out, _ = self.lstm(x)
        # Take the final timestep's hidden state.
        last = out[:, -1, :]                          # (batch, hidden)
        last = self.dropout(last)                     # MC Dropout site
        return self.fc(last)                          # (batch, 1)


def enable_mc_dropout(model: nn.Module) -> None:
    """Put `model` in eval mode, then re-enable dropout layers for MC sampling.

    BatchNorm and other train-only layers stay in eval mode (we'd never want
    BN's running statistics to drift during inference). Only dropout flips
    back on. Idempotent.
    """
    model.eval()
    for m in model.modules():
        if isinstance(m, nn.Dropout):
            m.train()


class TimeSeriesForecaster:
    """Train / evaluate / forecast wrapper around LSTMForecaster.

    Mirrors the shape of dl-mnist-cnn's DigitClassifier so PredictionService
    consumes both with the same train()/predict()/is_trained protocol.
    """

    def __init__(
        self,
        hidden_size: int = HIDDEN_SIZE,
        num_layers: int = NUM_LAYERS,
        dropout: float = DROPOUT,
    ):
        self._model = LSTMForecaster(hidden_size=hidden_size, num_layers=num_layers, dropout=dropout)
        self._trained = False
        self._epochs_run = 0
        self._best_val_loss: Optional[float] = None

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = DEFAULT_EPOCHS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        lr: float = LEARNING_RATE,
        patience: int = DEFAULT_PATIENCE,
    ) -> "TimeSeriesForecaster":
        """Train with optional early-stopping on val loss.

        X_train: (n, window_size) float32 — scaled trips
        y_train: (n, horizon=1) float32 — scaled next-day trips
        """
        x_tr = torch.from_numpy(X_train).float().unsqueeze(-1)  # (n, W, 1)
        y_tr = torch.from_numpy(y_train).float()                # (n, 1)
        loader = DataLoader(TensorDataset(x_tr, y_tr), batch_size=batch_size, shuffle=True)

        x_va = y_va = None
        if X_val is not None and y_val is not None and len(X_val) > 0:
            x_va = torch.from_numpy(X_val).float().unsqueeze(-1)
            y_va = torch.from_numpy(y_val).float()

        optimizer = torch.optim.Adam(self._model.parameters(), lr=lr)
        loss_fn = nn.MSELoss()
        best_val = float("inf")
        bad_epochs = 0

        for epoch in range(epochs):
            self._model.train()
            for xb, yb in loader:
                optimizer.zero_grad()
                pred = self._model(xb)
                loss = loss_fn(pred, yb)
                loss.backward()
                optimizer.step()
            self._epochs_run = epoch + 1

            if x_va is not None:
                self._model.eval()
                with torch.no_grad():
                    val_loss = loss_fn(self._model(x_va), y_va).item()
                if val_loss < best_val - 1e-6:
                    best_val = val_loss
                    bad_epochs = 0
                else:
                    bad_epochs += 1
                    if bad_epochs >= patience:
                        break
        self._best_val_loss = best_val if best_val < float("inf") else None
        self._trained = True
        return self

    def evaluate(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
        inverse_fn=None,
    ) -> Dict:
        """Evaluate on test set. If inverse_fn is given, reports MAPE/RMSE in
        original ride-count space; otherwise in model (scaled) space."""
        self._check_trained()
        x_te = torch.from_numpy(X_test).float().unsqueeze(-1)
        self._model.eval()
        with torch.no_grad():
            pred_scaled = self._model(x_te).numpy().reshape(-1)
        true_scaled = y_test.reshape(-1)
        if inverse_fn is not None:
            pred = inverse_fn(pred_scaled)
            true = inverse_fn(true_scaled)
        else:
            pred, true = pred_scaled, true_scaled
        rmse = float(np.sqrt(np.mean((pred - true) ** 2)))
        # MAPE — guarded against zero-truth division
        mask = np.abs(true) > 1e-6
        mape = float(np.mean(np.abs((true[mask] - pred[mask]) / true[mask]))) if mask.any() else 0.0
        return {
            "test_rmse": round(rmse, 4),
            "test_mape": round(mape, 4),
            "n_test": int(len(true)),
        }

    def forecast(
        self,
        seed_window: np.ndarray,
        horizon: int,
        n_samples: int = 30,
    ) -> Dict[str, np.ndarray]:
        """Autoregressive MC-Dropout forecast of length `horizon`.

        seed_window: (window_size,) float32 in SCALED space (caller pre-scales)
        Returns dict of arrays in SCALED space, all shape (horizon,) except
        `samples` which is (n_samples, horizon):
          mean   — average across MC samples per step
          lower  — mean - 2*std (95% band assuming Gaussian)
          upper  — mean + 2*std
          samples — full sample matrix (for downstream visualisation)
        Caller inverse-transforms back to ride-count space.
        """
        self._check_trained()
        if horizon < 1:
            raise ValueError(f"horizon must be ≥ 1, got {horizon}")
        if n_samples < 1:
            raise ValueError(f"n_samples must be ≥ 1, got {n_samples}")

        window_size = len(seed_window)
        enable_mc_dropout(self._model)

        samples = np.zeros((n_samples, horizon), dtype=np.float32)
        for s in range(n_samples):
            buf = list(seed_window)
            for step in range(horizon):
                x = torch.tensor(buf[-window_size:], dtype=torch.float32).reshape(1, window_size, 1)
                with torch.no_grad():
                    y = self._model(x).item()
                samples[s, step] = y
                buf.append(y)

        mean = samples.mean(axis=0)
        std = samples.std(axis=0)
        return {
            "mean": mean.astype(np.float32),
            "lower": (mean - 2 * std).astype(np.float32),
            "upper": (mean + 2 * std).astype(np.float32),
            "samples": samples,
        }

    @property
    def is_trained(self) -> bool:
        return self._trained

    @property
    def epochs_run(self) -> int:
        return self._epochs_run

    @property
    def best_val_loss(self) -> Optional[float]:
        return self._best_val_loss

    def _check_trained(self):
        if not self._trained:
            raise RuntimeError("Forecaster must be trained before calling evaluate/forecast.")
