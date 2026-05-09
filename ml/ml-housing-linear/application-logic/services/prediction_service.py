import logging
import os
from typing import Dict, List, Optional
import pandas as pd

from db_logic.loaders.loaders import LocalDataLoader
from db_logic.transforms.preprocessor import DataPreprocessor
from application_logic.model.classifier import HousingRegressor

logger = logging.getLogger(__name__)

_MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://ml-mlflow:5000")
_EXPERIMENT = "ml-housing-linear"


class PredictionService:
    """Trains HousingRegressor on startup and serves predictions."""

    def __init__(self):
        self._loader = LocalDataLoader()
        self._preprocessor = DataPreprocessor()
        self._regressor = HousingRegressor()
        self._metrics: Dict = {}
        self._train_size: int = 0
        self._test_size: int = 0
        self._run_id: Optional[str] = None
        self._experiment_id: Optional[str] = None
        self._ready = False

    def train(self) -> Dict:
        df = self._loader.load()
        X_train, X_test, y_train, y_test = self._loader.split(df)
        X_train_scaled = self._preprocessor.fit_transform(X_train)
        X_test_scaled = self._preprocessor.transform(X_test)
        self._regressor.train(X_train_scaled, y_train)
        self._metrics = self._regressor.evaluate(X_test_scaled, y_test)
        self._train_size = len(y_train)
        self._test_size = len(y_test)
        self._ready = True

        try:
            import mlflow
            import mlflow.sklearn
            mlflow.set_tracking_uri(_MLFLOW_URI)
            mlflow.set_experiment(_EXPERIMENT)
            with mlflow.start_run() as run:
                mlflow.log_params({
                    "model": "LinearRegression",
                    "dataset": "california_housing",
                    "n_samples": len(df),
                    "n_features": 8,
                    "test_size": 0.2,
                    "random_state": 42,
                })
                mlflow.log_metrics(self._metrics)
                self._run_id = run.info.run_id
                self._experiment_id = str(run.info.experiment_id)
                try:
                    mlflow.sklearn.log_model(self._regressor._model, "model")
                except Exception as artifact_err:
                    logger.warning(f"MLflow artifact logging skipped: {artifact_err}")
        except Exception as e:
            logger.warning(f"MLflow logging skipped: {e}")

        return self._metrics

    def predict(self, features: List[float]) -> Dict:
        if not self._ready:
            self.train()
        X = pd.DataFrame([features], columns=self._loader.get_feature_names())
        X_scaled = self._preprocessor.transform(X)
        value = self._regressor.predict(X_scaled)[0]
        usd = f"${value * 100_000:,.0f}"
        return {
            "prediction": round(value, 4),
            "prediction_usd": usd,
            "unit": "$100,000s",
            "metrics": self._metrics,
        }

    def get_model_info(self) -> Dict:
        if not self._ready:
            self.train()
        m = self._metrics
        return {
            "model_type": "LinearRegression",
            "dataset": "California Housing",
            "n_samples": 20640,
            "n_features": 8,
            "parameters": {
                "model": "LinearRegression",
                "test_size": 0.2,
                "random_state": 42,
            },
            "metrics": m,
            "metrics_display": {
                "rmse": f"{m['rmse']:.4f}",
                "mae":  f"{m['mae']:.4f}",
                "r2":   f"{m['r2']:.4f}",
            },
            "split": {
                "train_samples": self._train_size,
                "test_samples": self._test_size,
            },
            "run_id": self._run_id,
            "experiment_id": self._experiment_id,
            "mlflow_url": (
                f"/mlflow/#/experiments/{self._experiment_id}/runs/{self._run_id}"
                if self._run_id else None
            ),
        }

    @property
    def is_ready(self) -> bool:
        return self._ready
