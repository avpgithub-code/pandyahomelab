"""Prediction service: orchestrates loader -> preprocessor -> model -> MLflow.

The single object the API layer talks to. Same shape as dl/dl-lstm-forecast:
thread-safe lazy training (eager warm-up at startup; concurrent /predict calls
during the train window block on a lock instead of stampeding), a /model-info
payload that fills the About drawer's {{tokens}}, and MLflow logging that
degrades gracefully — the demo still serves predictions if nlp-mlflow is
briefly unreachable.
"""
import json
import logging
import os
import tempfile
import threading
import time
from typing import Dict, Optional

import pandas as pd

from application_logic.model.classifier import (
    ARCHITECTURE,
    C,
    MAX_FEATURES,
    NGRAM_RANGE,
    TextClassifier,
)
from db_logic.loaders.loaders import TextLoader
from db_logic.transforms.preprocessor import TextPreprocessor
from shared.config import get_config

logger = logging.getLogger(__name__)

_config = get_config()
_MLFLOW_URI = _config.MLFLOW_TRACKING_URI
_MLFLOW_PUBLIC_BASE = _config.MLFLOW_PUBLIC_BASE_URL
# Experiment per demo, named after the container (Phase 3 plan).
_EXPERIMENT = "nlp-quora-randomforest"
_DATASET = "Built-in sample corpus (template placeholder)"

DEFAULT_TEST_SIZE = 0.25


class PredictionService:
    """End-to-end orchestration for the nlp-quora-randomforest demo."""

    def __init__(
        self,
        loader: Optional[TextLoader] = None,
        test_size: float = DEFAULT_TEST_SIZE,
    ):
        self._loader = loader or TextLoader()
        self._preprocessor = TextPreprocessor()
        self._model = TextClassifier()
        self._test_size = test_size
        self._metrics: Dict = {}
        self._confusion_matrix: list = []
        self._train_size = 0
        self._test_count = 0
        self._train_seconds = 0.0
        self._run_id: Optional[str] = None
        self._experiment_id: Optional[str] = None
        self._ready = False
        self._train_lock = threading.Lock()

    def train(self, df: Optional[pd.DataFrame] = None) -> Dict:
        """Fit on the train split, evaluate on the test split, log to MLflow.

        Thread-safe — concurrent callers during the warm-up window block here
        and pick up the cached metrics once the first caller finishes.
        """
        with self._train_lock:
            if self._ready:
                return self._metrics

            start = time.perf_counter()
            split = self._loader.train_test_split(test_size=self._test_size, df=df)
            x_train = self._preprocessor.transform_many(split.train["text"].tolist())
            x_test = self._preprocessor.transform_many(split.test["text"].tolist())

            self._model.fit(x_train, split.train["label"].tolist())
            result = self._model.evaluate(x_test, split.test["label"].tolist())
            self._metrics = result["metrics"]
            self._confusion_matrix = result["confusion_matrix"]

            self._train_size = len(split.train)
            self._test_count = len(split.test)
            self._train_seconds = time.perf_counter() - start
            self._ready = True

            self._log_to_mlflow()
            return self._metrics

    def predict(self, text: str) -> Dict:
        if not self._ready:
            self.train()
        clean = self._preprocessor.transform(text)
        probs = self._model.predict_proba([clean])[0]
        best = int(probs.argmax())
        return {
            "label": self._model.labels[best],
            "confidence": round(float(probs[best]), 4),
            "probabilities": {
                label: round(float(p), 4) for label, p in zip(self._model.labels, probs)
            },
            "pipeline": self._preprocessor.trace(text),
        }

    def get_model_info(self) -> Dict:
        """Model metadata for the About drawer and Model Card.

        DOES NOT trigger training — Cloudflare caps origin responses at 100s, so
        a metadata endpoint never trains (Phase 2a lesson). Before training it
        returns the static fields with empty metrics.
        """
        info = {
            "model_type": "TextClassifier",
            "architecture": ARCHITECTURE,
            "dataset": _DATASET,
            "target": "text label (classification)",
            "parameters": {
                "ngram_range": list(NGRAM_RANGE),
                "max_features": MAX_FEATURES,
                "C": C,
                "test_size": self._test_size,
            },
            "preprocessing": {"steps": self._preprocessor.step_names},
            "metrics": {},
            "metrics_display": {},
            "confusion_matrix": None,
            "split": None,
            "training": None,
            "run_id": None,
            "experiment_id": None,
            "mlflow_url": None,
        }
        if not self._ready:
            return info
        m = self._metrics
        info.update({
            "metrics": m,
            "metrics_display": {
                "accuracy": f"{m['accuracy'] * 100:.1f}%",
                "precision_macro": f"{m['precision_macro']:.3f}",
                "recall_macro": f"{m['recall_macro']:.3f}",
                "f1_macro": f"{m['f1_macro']:.3f}",
            },
            "confusion_matrix": {
                "labels": self._model.labels,
                "matrix": self._confusion_matrix,
            },
            "split": {
                "train_samples": self._train_size,
                "test_samples": self._test_count,
            },
            "training": {
                "seconds": f"{self._train_seconds:.1f}s",
                "vocabulary_size": self._model.vocabulary_size,
            },
            "run_id": self._run_id,
            "experiment_id": self._experiment_id,
            "mlflow_url": (
                f"{_MLFLOW_PUBLIC_BASE}/#/experiments/{self._experiment_id}/runs/{self._run_id}"
                if self._run_id else None
            ),
        })
        return info

    @property
    def is_ready(self) -> bool:
        return self._ready

    def _log_to_mlflow(self) -> None:
        """Log params, metrics and the model file to nlp-mlflow.

        Uses the classic per-run `mlflow.log_artifact` path, NOT the LoggedModel
        API (`mlflow.sklearn.log_model`): MLflow 3.11's LoggedModel +
        `--serve-artifacts` silently fails uploads on the per-domain trackers
        (Phase 2b.10 lesson, see mlflow_operational_lessons). run_id is captured
        before the artifact write so a failed upload still links the run.
        """
        try:
            import mlflow
            mlflow.set_tracking_uri(_MLFLOW_URI)
            mlflow.set_experiment(_EXPERIMENT)
            with mlflow.start_run() as run:
                mlflow.log_params({
                    "architecture": ARCHITECTURE,
                    "ngram_range": str(NGRAM_RANGE),
                    "max_features": MAX_FEATURES,
                    "C": C,
                    "test_size": self._test_size,
                    "n_train": self._train_size,
                    "n_test": self._test_count,
                    "preprocessing": ",".join(self._preprocessor.step_names),
                    "dataset": _DATASET,
                })
                mlflow.log_metrics({
                    **self._metrics,
                    "train_seconds": round(self._train_seconds, 3),
                    "vocabulary_size": self._model.vocabulary_size,
                })
                self._run_id = run.info.run_id
                self._experiment_id = str(run.info.experiment_id)
                try:
                    with tempfile.TemporaryDirectory() as tmp:
                        model_path = os.path.join(tmp, "model.joblib")
                        self._model.save(model_path)
                        mlflow.log_artifact(model_path, artifact_path="model")
                        # Confusion matrix as a JSON artifact (the costly error
                        # is visible in MLflow, not only in the drawer).
                        cm_path = os.path.join(tmp, "confusion_matrix.json")
                        with open(cm_path, "w") as f:
                            json.dump(
                                {"labels": self._model.labels, "matrix": self._confusion_matrix}, f
                            )
                        mlflow.log_artifact(cm_path, artifact_path="evaluation")
                except Exception as artifact_err:
                    logger.warning(f"MLflow artifact logging skipped: {artifact_err}")
        except Exception as e:
            logger.warning(f"MLflow logging skipped: {e}")
