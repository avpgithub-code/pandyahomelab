"""Prediction service: orchestrates data loading, preprocessing, and prediction."""
import logging
import os
from typing import Dict, List, Optional

from db_logic.loaders.loaders import LocalDataLoader
from db_logic.transforms.preprocessor import DataPreprocessor
from application_logic.model.classifier import IrisClassifier

logger = logging.getLogger(__name__)

_MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://ml-mlflow:5000")
_EXPERIMENT = "ml-iris-knn"


class PredictionService:
    """Handles end-to-end prediction requests for Iris classification."""

    def __init__(self):
        self._loader = LocalDataLoader()
        self._preprocessor = DataPreprocessor()
        self._classifier = IrisClassifier(n_neighbors=3)
        self._metrics: Dict = {}
        self._run_id: Optional[str] = None
        self._experiment_id: Optional[str] = None
        self._ready = False

    def train(self) -> Dict:
        df = self._loader.load()
        X_train, X_test, y_train, y_test = self._loader.split(df)
        X_train_scaled = self._preprocessor.fit_transform(X_train)
        X_test_scaled = self._preprocessor.transform(X_test)
        self._classifier.train(X_train_scaled, y_train)
        self._metrics = self._classifier.evaluate(X_test_scaled, y_test)
        self._ready = True

        try:
            import mlflow
            import mlflow.sklearn
            mlflow.set_tracking_uri(_MLFLOW_URI)
            mlflow.set_experiment(_EXPERIMENT)
            with mlflow.start_run() as run:
                mlflow.log_params({
                    "n_neighbors": 3,
                    "algorithm": "ball_tree",
                    "dataset": "iris",
                    "n_samples": len(df),
                    "n_features": 4,
                    "test_size": 0.2,
                })
                mlflow.log_metrics(self._metrics)
                mlflow.sklearn.log_model(self._classifier._model, "model")
                self._run_id = run.info.run_id
                self._experiment_id = str(run.info.experiment_id)
        except Exception as e:
            logger.warning(f"MLflow logging skipped: {e}")

        return self._metrics

    def predict(self, features: List[float]) -> Dict:
        if not self._ready:
            self.train()
        import pandas as pd
        X = pd.DataFrame([features], columns=self._loader.get_feature_names())
        X_scaled = self._preprocessor.transform(X)
        prediction = self._classifier.predict(X_scaled)[0]
        probabilities = self._classifier.predict_proba(X_scaled)[0]
        return {
            "prediction": prediction,
            "species": IrisClassifier.CLASSES[prediction],
            "confidence": round(max(probabilities), 4),
            "probabilities": {
                IrisClassifier.CLASSES[i]: round(p, 4)
                for i, p in enumerate(probabilities)
            },
        }

    def get_model_info(self) -> Dict:
        if not self._ready:
            self.train()
        return {
            "model_type": "KNeighborsClassifier",
            "dataset": "Iris",
            "n_samples": 150,
            "n_features": 4,
            "classes": list(IrisClassifier.CLASSES.values()),
            "parameters": {"n_neighbors": 3, "algorithm": "ball_tree"},
            "metrics": self._metrics,
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
