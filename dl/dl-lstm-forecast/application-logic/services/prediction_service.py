"""Prediction service: orchestrates loader -> scaler -> forecaster -> MLflow.

Composes the three db-logic and one application-logic primitives into the
single object the API layer talks to. Manages thread-safe lazy training
(eager warm-up at startup; concurrent /forecast calls during the train
window block on a lock instead of stampeding), and produces forecast
payloads in ride-count space with optional actuals overlay when the
visitor's anchor date is inside the historical range.

MLflow failures degrade gracefully — the demo still serves forecasts if
dl-mlflow is briefly unreachable.
"""
import logging
import os
import threading
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from application_logic.model.forecaster import (
    ARCHITECTURE,
    DEFAULT_BATCH_SIZE,
    DEFAULT_EPOCHS,
    DEFAULT_PATIENCE,
    DROPOUT,
    HIDDEN_SIZE,
    LEARNING_RATE,
    NUM_LAYERS,
    TimeSeriesForecaster,
)
from db_logic.loaders.loaders import BikeShareLoader
from db_logic.transforms.preprocessor import WindowScaler, make_windows

logger = logging.getLogger(__name__)

_MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://dl-mlflow:5000")
_MLFLOW_PUBLIC_BASE = os.environ.get(
    "MLFLOW_PUBLIC_BASE_URL", "https://mlflow-dl.pandyahomelab.com"
)
_EXPERIMENT = "dl-lstm-forecast"

# Per configs/training.yaml — duplicated here as defaults so PredictionService
# is self-contained for tests; production code path reads the YAML in main.py.
DEFAULT_WINDOW_SIZE = 28
DEFAULT_VAL_DAYS = 90
DEFAULT_TEST_DAYS = 180
DEFAULT_MC_SAMPLES = 30
DEFAULT_FORECAST_HORIZON = 14


class PredictionService:
    """End-to-end orchestration for the dl-lstm-forecast demo."""

    def __init__(
        self,
        loader: Optional[BikeShareLoader] = None,
        window_size: int = DEFAULT_WINDOW_SIZE,
        val_days: int = DEFAULT_VAL_DAYS,
        test_days: int = DEFAULT_TEST_DAYS,
        mc_samples: int = DEFAULT_MC_SAMPLES,
        forecast_horizon: int = DEFAULT_FORECAST_HORIZON,
    ):
        self._loader = loader or BikeShareLoader()
        self._scaler = WindowScaler()
        self._forecaster = TimeSeriesForecaster()
        self._window_size = window_size
        self._val_days = val_days
        self._test_days = test_days
        self._mc_samples = mc_samples
        self._forecast_horizon = forecast_horizon
        self._metrics: Dict = {}
        self._train_size = 0
        self._val_size = 0
        self._test_size = 0
        self._run_id: Optional[str] = None
        self._experiment_id: Optional[str] = None
        self._ready = False
        # See 2a's [[phase_2a_complete]] — thread-safe re-entry guard.
        self._train_lock = threading.Lock()

    def train(
        self,
        epochs: int = DEFAULT_EPOCHS,
        patience: int = DEFAULT_PATIENCE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        df: Optional[pd.DataFrame] = None,
        val_days: Optional[int] = None,
        test_days: Optional[int] = None,
    ) -> Dict:
        """Train the forecaster on the loaded daily-counts series and log to MLflow.

        Args allow tests to inject a tiny synthetic frame + short epochs.
        Thread-safe — concurrent callers during the warm-up window block here
        and pick up the cached metrics once the first caller finishes.
        """
        with self._train_lock:
            if self._ready:
                return self._metrics

            df = df if df is not None else self._loader.load_daily_counts()
            val_days = val_days if val_days is not None else self._val_days
            test_days = test_days if test_days is not None else self._test_days
            split = self._loader.train_val_test_split(
                val_days=val_days, test_days=test_days, df=df
            )

            train_series = split.train["trips"].to_numpy(dtype=np.float32)
            val_series = split.val["trips"].to_numpy(dtype=np.float32)
            test_series = split.test["trips"].to_numpy(dtype=np.float32)

            self._scaler.fit(train_series)
            train_scaled = self._scaler.transform(train_series)
            val_scaled = self._scaler.transform(val_series)
            test_scaled = self._scaler.transform(test_series)

            X_tr, y_tr = make_windows(train_scaled, window_size=self._window_size, horizon=1)
            X_va, y_va = make_windows(val_scaled, window_size=self._window_size, horizon=1)
            X_te, y_te = make_windows(test_scaled, window_size=self._window_size, horizon=1)

            self._forecaster.train(
                X_tr, y_tr, X_va, y_va, epochs=epochs, batch_size=batch_size, patience=patience
            )
            self._metrics = self._forecaster.evaluate(X_te, y_te, inverse_fn=self._scaler.inverse_transform)
            self._metrics["best_val_loss"] = (
                round(float(self._forecaster.best_val_loss), 6)
                if self._forecaster.best_val_loss is not None
                else None
            )
            self._metrics["epochs_run"] = self._forecaster.epochs_run

            self._train_size = len(split.train)
            self._val_size = len(split.val)
            self._test_size = len(split.test)
            self._epochs_requested = epochs
            self._patience = patience
            self._batch_size = batch_size
            self._ready = True

            self._log_to_mlflow(df=df)
            return self._metrics

    def forecast(
        self,
        anchor_date,
        horizon: Optional[int] = None,
        n_samples: Optional[int] = None,
    ) -> Dict:
        """Produce a `horizon`-step forecast anchored at `anchor_date`.

        If the anchor + horizon range falls inside the historical series,
        each forecast point includes an `actual` value so the UI can render
        a compare-to-actuals overlay. If the range extends past the latest
        observation, those points have `actual = None`.

        Returned dict shape (caller serialises to JSON):
        {
          "anchor_date": "YYYY-MM-DD",
          "horizon": 14,
          "window_size": 28,
          "points": [
            {"day_offset": 1, "date": "YYYY-MM-DD",
             "mean": <ride_count>, "lower": <>, "upper": <>,
             "actual": <int|None>}, ...
          ]
        }
        """
        if not self._ready:
            self.train()
        horizon = horizon if horizon is not None else self._forecast_horizon
        n_samples = n_samples if n_samples is not None else self._mc_samples

        df = self._loader.load_daily_counts()
        resolved_anchor, seed = self._loader.get_window_at(
            anchor_date, window_size=self._window_size, df=df
        )
        seed_scaled = self._scaler.transform(seed)
        result = self._forecaster.forecast(seed_scaled, horizon=horizon, n_samples=n_samples)
        mean = self._scaler.inverse_transform(result["mean"])
        lower = self._scaler.inverse_transform(result["lower"])
        upper = self._scaler.inverse_transform(result["upper"])

        points: List[Dict] = []
        for i in range(horizon):
            forecast_date = resolved_anchor + pd.Timedelta(days=i + 1)
            actual: Optional[int] = None
            if forecast_date in df.index:
                actual = int(df.loc[forecast_date, "trips"])
            points.append(
                {
                    "day_offset": i + 1,
                    "date": forecast_date.strftime("%Y-%m-%d"),
                    "mean": int(round(float(mean[i]))),
                    "lower": int(round(float(lower[i]))),
                    "upper": int(round(float(upper[i]))),
                    "actual": actual,
                }
            )
        return {
            "anchor_date": resolved_anchor.strftime("%Y-%m-%d"),
            "horizon": horizon,
            "window_size": self._window_size,
            "points": points,
        }

    def get_history(self) -> Dict:
        """Full historical series for the UI's background chart.

        Returns {"dates": [...], "trips": [...], "min_anchor": "YYYY-MM-DD",
                 "max_anchor": "YYYY-MM-DD"} where min_anchor is the earliest
        date that has window_size days of preceding history (so the date
        picker can clamp to valid anchors).
        """
        df = self._loader.load_daily_counts()
        min_anchor = df.index[self._window_size - 1]
        return {
            "dates": [d.strftime("%Y-%m-%d") for d in df.index],
            "trips": [int(v) for v in df["trips"].to_numpy()],
            "min_anchor": min_anchor.strftime("%Y-%m-%d"),
            "max_anchor": df.index.max().strftime("%Y-%m-%d"),
        }

    def get_model_info(self) -> Dict:
        """Model metadata for the demo's About drawer / Model Card.

        DOES NOT trigger training (Cloudflare's free tier caps origin
        response at 100s; full LSTM train is ~10–60s but the safe pattern
        from 2a's [[phase_2a_complete]] is to never auto-train from
        /model-info). Returns architectural metadata + empty metrics when
        the model isn't trained yet.
        """
        params = {
            "window_size": self._window_size,
            "hidden_size": HIDDEN_SIZE,
            "num_layers": NUM_LAYERS,
            "dropout": DROPOUT,
            "optimizer": "adam",
            "learning_rate": LEARNING_RATE,
            "loss": "mse",
            "mc_samples": self._mc_samples,
            "forecast_horizon": self._forecast_horizon,
        }
        if not self._ready:
            return {
                "model_type": "LSTMForecaster",
                "architecture": ARCHITECTURE,
                "dataset": "NYC CitiBike daily ride counts (toddwschneider/nyc-citibike-data)",
                "target": "daily ride count (regression)",
                "parameters": params,
                "metrics": {},
                "metrics_display": {},
                "split": None,
                "run_id": None,
                "experiment_id": None,
                "mlflow_url": None,
            }
        m = self._metrics
        return {
            "model_type": "LSTMForecaster",
            "architecture": ARCHITECTURE,
            "dataset": "NYC CitiBike daily ride counts (toddwschneider/nyc-citibike-data)",
            "target": "daily ride count (regression)",
            "parameters": params,
            "metrics": m,
            "metrics_display": {
                "test_mape": f"{m.get('test_mape', 0.0) * 100:.1f}%",
                "test_rmse": f"{m.get('test_rmse', 0.0):.0f} rides/day",
                "epochs_run": str(m.get("epochs_run", 0)),
            },
            "split": {
                "train_samples": self._train_size,
                "val_samples": self._val_size,
                "test_samples": self._test_size,
            },
            "run_id": self._run_id,
            "experiment_id": self._experiment_id,
            "mlflow_url": (
                f"{_MLFLOW_PUBLIC_BASE}/#/experiments/{self._experiment_id}/runs/{self._run_id}"
                if self._run_id else None
            ),
        }

    @property
    def is_ready(self) -> bool:
        return self._ready

    def _log_to_mlflow(self, df: Optional[pd.DataFrame] = None) -> None:
        """Capture run_id BEFORE log_model — model artifact logging can throw.

        Lesson from [[mlflow_operational_lessons]] (Phase 1c).
        """
        try:
            import mlflow
            import mlflow.pytorch
            mlflow.set_tracking_uri(_MLFLOW_URI)
            mlflow.set_experiment(_EXPERIMENT)
            with mlflow.start_run() as run:
                mlflow.log_params({
                    "architecture": ARCHITECTURE,
                    "window_size": self._window_size,
                    "hidden_size": HIDDEN_SIZE,
                    "num_layers": NUM_LAYERS,
                    "dropout": DROPOUT,
                    "optimizer": "adam",
                    "learning_rate": LEARNING_RATE,
                    "loss": "mse",
                    "epochs_requested": self._epochs_requested,
                    "patience": self._patience,
                    "batch_size": self._batch_size,
                    "val_days": self._val_days,
                    "test_days": self._test_days,
                    "n_train": self._train_size,
                    "n_val": self._val_size,
                    "n_test": self._test_size,
                    "mc_samples": self._mc_samples,
                    "forecast_horizon": self._forecast_horizon,
                    "dataset": "NYC CitiBike daily (toddwschneider)",
                })
                # log_metrics skips Nones — drop best_val_loss if missing.
                metrics = {k: v for k, v in self._metrics.items() if v is not None}
                mlflow.log_metrics(metrics)
                self._run_id = run.info.run_id
                self._experiment_id = str(run.info.experiment_id)
                try:
                    mlflow.pytorch.log_model(self._forecaster._model, "model")
                except Exception as artifact_err:
                    logger.warning(f"MLflow artifact logging skipped: {artifact_err}")
        except Exception as e:
            logger.warning(f"MLflow logging skipped: {e}")
