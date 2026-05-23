"""Prediction service: orchestrates loader -> classifier -> MLflow tracking.

Lazy-trains the CNN on first predict() call and logs the run to dl-mlflow
(separate per-domain MLflow tracker, exposed at mlflow-dl.pandyahomelab.com
in production). MLflow failures degrade gracefully — the demo still serves
predictions if the tracker is briefly unreachable.
"""
import logging
import os
from typing import Dict, List, Optional

from db_logic.loaders.loaders import LocalDataLoader
from db_logic.transforms.preprocessor import DataPreprocessor
from application_logic.model.classifier import (
    ARCHITECTURE,
    DEFAULT_EPOCHS,
    DigitClassifier,
    LEARNING_RATE,
)

logger = logging.getLogger(__name__)

_MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://dl-mlflow:5000")
_MLFLOW_PUBLIC_BASE = os.environ.get(
    "MLFLOW_PUBLIC_BASE_URL", "https://mlflow-dl.pandyahomelab.com"
)
_EXPERIMENT = "dl-mnist-cnn"


class PredictionService:
    """End-to-end orchestration for the dl-mnist-cnn demo."""

    def __init__(self):
        self._loader = LocalDataLoader()
        self._preprocessor = DataPreprocessor()
        self._classifier = DigitClassifier()
        self._metrics: Dict = {}
        self._train_size: int = 0
        self._test_size: int = 0
        self._epochs: int = DEFAULT_EPOCHS
        self._run_id: Optional[str] = None
        self._experiment_id: Optional[str] = None
        self._ready = False

    def train(
        self,
        epochs: Optional[int] = None,
        train_loader=None,
        test_loader=None,
    ) -> Dict:
        """Train and evaluate. Args allow tests to inject tiny loaders / 1 epoch."""
        epochs = epochs if epochs is not None else DEFAULT_EPOCHS
        train_loader = train_loader if train_loader is not None else self._loader.load_train()
        test_loader = test_loader if test_loader is not None else self._loader.load_test()

        self._classifier.train(train_loader, epochs=epochs)
        self._metrics = self._classifier.evaluate(test_loader)
        self._train_size = len(train_loader.dataset)
        self._test_size = len(test_loader.dataset)
        self._epochs = epochs
        self._ready = True

        self._log_to_mlflow()
        return self._metrics

    def predict(self, pixels: List[float]) -> Dict:
        if not self._ready:
            self.train()
        tensor = self._preprocessor.transform_input(pixels)
        return self._classifier.predict(tensor)

    def get_model_info(self) -> Dict:
        if not self._ready:
            self.train()
        m = self._metrics
        return {
            "model_type": "MnistCNN",
            "architecture": ARCHITECTURE,
            "dataset": "MNIST",
            "classes": list(DigitClassifier.CLASSES),
            "parameters": {
                "epochs": self._epochs,
                "optimizer": "adam",
                "learning_rate": LEARNING_RATE,
                "loss": "cross_entropy",
            },
            "metrics": m,
            "metrics_display": {
                "accuracy": f"{m.get('accuracy', 0.0) * 100:.1f}%",
                "correct": str(m.get("correct", 0)),
                "total": str(m.get("total", 0)),
            },
            "split": {
                "train_samples": self._train_size,
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

    def _log_to_mlflow(self) -> None:
        """Capture run_id BEFORE logging the model — log_model can throw."""
        try:
            import mlflow
            import mlflow.pytorch
            mlflow.set_tracking_uri(_MLFLOW_URI)
            mlflow.set_experiment(_EXPERIMENT)
            with mlflow.start_run() as run:
                mlflow.log_params({
                    "architecture": ARCHITECTURE,
                    "optimizer": "adam",
                    "learning_rate": LEARNING_RATE,
                    "loss": "cross_entropy",
                    "epochs": self._epochs,
                    "n_train": self._train_size,
                    "n_test": self._test_size,
                    "dataset": "MNIST",
                })
                mlflow.log_metrics(self._metrics)
                self._run_id = run.info.run_id
                self._experiment_id = str(run.info.experiment_id)
                try:
                    mlflow.pytorch.log_model(self._classifier._model, "model")
                except Exception as artifact_err:
                    logger.warning(f"MLflow artifact logging skipped: {artifact_err}")
        except Exception as e:
            logger.warning(f"MLflow logging skipped: {e}")
