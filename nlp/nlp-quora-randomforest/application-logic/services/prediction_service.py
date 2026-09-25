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

from application_logic.model.classifier import (
    ARCHITECTURE,
    BOW_MAX_FEATURES,
    MIN_SAMPLES_LEAF,
    N_ESTIMATORS,
    DuplicateClassifier,
)
from db_logic.loaders.quora import GLUE_REPO, GLUE_REVISION, PairSplit, QuoraPairLoader
from db_logic.transforms.features import FEATURE_GROUPS, PairFeatureBuilder
from db_logic.transforms.preprocessor import TextPreprocessor
from shared.config import get_config

logger = logging.getLogger(__name__)

_config = get_config()
_MLFLOW_URI = _config.MLFLOW_TRACKING_URI
_MLFLOW_PUBLIC_BASE = _config.MLFLOW_PUBLIC_BASE_URL
# Experiment per demo, named after the container (Phase 3 plan).
_EXPERIMENT = "nlp-quora-randomforest"
_DATASET = f"Quora Question Pairs (GLUE QQP, {GLUE_REPO}@{GLUE_REVISION[:7]})"

DEFAULT_THRESHOLD = 0.5


class PredictionService:
    """End-to-end orchestration for the nlp-quora-randomforest demo."""

    def __init__(
        self,
        loader: Optional[QuoraPairLoader] = None,
        max_train_rows: Optional[int] = _config.QQP_MAX_TRAIN_ROWS,
        max_test_rows: Optional[int] = _config.QQP_MAX_TEST_ROWS,
        features: Optional[PairFeatureBuilder] = None,
    ):
        self._loader = loader or QuoraPairLoader(_config.QQP_DATA_DIR)
        self._max_train_rows = max_train_rows
        self._max_test_rows = max_test_rows
        self._preprocessor = TextPreprocessor()
        self._features = features or PairFeatureBuilder()
        self._model = DuplicateClassifier()
        self._metrics: Dict = {}
        self._confusion_matrix: list = []
        self._train_size = 0
        self._test_count = 0
        self._train_seconds = 0.0
        self._run_id: Optional[str] = None
        self._experiment_id: Optional[str] = None
        self._ready = False
        self._train_lock = threading.Lock()

    def train(self, split: Optional[PairSplit] = None) -> Dict:
        """Fit on GLUE train, evaluate on GLUE validation, log to MLflow.

        Thread-safe — concurrent callers during the warm-up window block here
        and pick up the cached metrics once the first caller finishes.
        """
        with self._train_lock:
            if self._ready:
                return self._metrics

            start = time.perf_counter()
            split = split or self._loader.train_test_split(
                max_train_rows=self._max_train_rows, max_test_rows=self._max_test_rows
            )
            train_q1, train_q2, train_x = self._featurize(split.train)
            test_q1, test_q2, test_x = self._featurize(split.test)

            self._model.fit(train_q1, train_q2, train_x, split.train["is_duplicate"].tolist())
            result = self._model.evaluate(
                test_q1, test_q2, test_x, split.test["is_duplicate"].tolist(), DEFAULT_THRESHOLD
            )
            self._metrics = result["metrics"]
            self._confusion_matrix = result["confusion_matrix"]

            self._train_size = len(split.train)
            self._test_count = len(split.test)
            self._train_seconds = time.perf_counter() - start
            self._ready = True

            self._log_to_mlflow()
            return self._metrics

    def predict(self, question1: str, question2: str) -> Dict:
        """P(duplicate) plus everything the UI needs to explain it.

        The label uses the default 0.5 threshold; the UI's slider re-labels
        client-side from `probability`, so moving it never costs a request.
        """
        if not self._ready:
            self.train()
        q1 = self._preprocessor.transform(question1)
        q2 = self._preprocessor.transform(question2)
        values = self._features.build(q1, q2)
        proba = float(self._model.predict_proba([q1], [q2], self._features.build_matrix([q1], [q2]))[0])
        return {
            "probability": round(proba, 4),
            "threshold": DEFAULT_THRESHOLD,
            "label": self._model.labels[int(proba >= DEFAULT_THRESHOLD)],
            "features": {
                group: {name: round(float(values[name]), 4) for name in names}
                for group, names in FEATURE_GROUPS.items()
            },
            "pipeline": {
                "question1": self._preprocessor.trace(question1),
                "question2": self._preprocessor.trace(question2),
            },
        }

    def _featurize(self, df):
        q1 = self._preprocessor.transform_many(df["question1"].tolist())
        q2 = self._preprocessor.transform_many(df["question2"].tolist())
        return q1, q2, self._features.build_matrix(q1, q2)

    def get_model_info(self) -> Dict:
        """Model metadata for the About drawer and Model Card.

        DOES NOT trigger training — Cloudflare caps origin responses at 100s, so
        a metadata endpoint never trains (Phase 2a lesson). Before training it
        returns the static fields with empty metrics.
        """
        info = {
            "model_type": "RandomForestClassifier",
            "architecture": ARCHITECTURE,
            "dataset": _DATASET,
            "target": "is_duplicate (binary)",
            "parameters": {
                "bow_max_features": BOW_MAX_FEATURES,
                "n_estimators": N_ESTIMATORS,
                "min_samples_leaf": MIN_SAMPLES_LEAF,
                "max_train_rows": self._max_train_rows,
                "threshold": DEFAULT_THRESHOLD,
            },
            "preprocessing": {"steps": self._preprocessor.step_names},
            "features": FEATURE_GROUPS,
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
                "precision": f"{m['precision']:.3f}",
                "recall": f"{m['recall']:.3f}",
                "f1": f"{m['f1']:.3f}",
                "roc_auc": f"{m['roc_auc']:.3f}",
                "log_loss": f"{m['log_loss']:.3f}",
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
                    "bow_max_features": BOW_MAX_FEATURES,
                    "n_estimators": N_ESTIMATORS,
                    "min_samples_leaf": MIN_SAMPLES_LEAF,
                    "threshold": DEFAULT_THRESHOLD,
                    "n_handcrafted_features": sum(len(g) for g in FEATURE_GROUPS.values()),
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
