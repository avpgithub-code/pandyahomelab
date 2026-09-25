"""Prediction service: loader -> preprocessor -> four representations -> MLflow.

Same shape as nlp-quora-randomforest: thread-safe lazy training (eager warm-up at
startup; concurrent calls during the train window block on a lock), a /model-info
payload that fills the About drawer's {{tokens}}, and MLflow logging that degrades
gracefully if nlp-mlflow is briefly unreachable.
"""
import json
import logging
import os
import tempfile
import threading
import time
from typing import Dict, Optional

from application_logic.model.representations import (
    C,
    MIN_DF,
    NGRAM_MAX_FEATURES,
    REPRESENTATIONS,
    SOLVER,
    RepresentationSuite,
)
from db_logic.loaders.imdb import IMDB_REPO, IMDB_REVISION, ImdbLoader, Split
from db_logic.transforms.preprocessor import TextPreprocessor
from db_logic.transforms.tokens import TokenAnalyzer
from shared.config import get_config

logger = logging.getLogger(__name__)

_config = get_config()
_MLFLOW_URI = _config.MLFLOW_TRACKING_URI
_MLFLOW_PUBLIC_BASE = _config.MLFLOW_PUBLIC_BASE_URL
# Experiment per demo, named after the container (Phase 3 plan).
_EXPERIMENT = "nlp-imdb-textrep"
_DATASET = f"IMDB Large Movie Review Dataset ({IMDB_REPO}@{IMDB_REVISION[:7]})"
ARCHITECTURE = "4 representations (one-hot, BoW, n-grams, TF-IDF) -> LogisticRegression each"


class PredictionService:
    """End-to-end orchestration for the nlp-imdb-textrep demo."""

    def __init__(
        self,
        loader: Optional[ImdbLoader] = None,
        max_train_rows: Optional[int] = _config.IMDB_MAX_TRAIN_ROWS,
        max_test_rows: Optional[int] = _config.IMDB_MAX_TEST_ROWS,
        tokens: Optional[TokenAnalyzer] = None,
    ):
        self._loader = loader or ImdbLoader(_config.IMDB_DATA_DIR)
        self._max_train_rows = max_train_rows
        self._max_test_rows = max_test_rows
        self._preprocessor = TextPreprocessor()
        self._tokens = tokens or TokenAnalyzer()
        self._suite = RepresentationSuite()
        self._results: Dict = {}
        self._train_size = 0
        self._test_count = 0
        self._train_seconds = 0.0
        self._model_size_mb = 0.0
        self._run_id: Optional[str] = None
        self._experiment_id: Optional[str] = None
        self._ready = False
        self._train_lock = threading.Lock()

    def train(self, split: Optional[Split] = None) -> Dict:
        """Fit every representation on IMDB train, evaluate on IMDB test, log to MLflow.

        Thread-safe — concurrent callers during the warm-up window block here
        and pick up the cached results once the first caller finishes.
        """
        with self._train_lock:
            if self._ready:
                return self._results

            start = time.perf_counter()
            self._tokens.load()
            split = split or self._loader.train_test_split(
                max_train_rows=self._max_train_rows, max_test_rows=self._max_test_rows
            )
            train_x = self._preprocessor.transform_many(split.train["text"].tolist())
            test_x = self._preprocessor.transform_many(split.test["text"].tolist())
            self._suite.fit(train_x, split.train["label"].tolist())
            self._results = self._suite.evaluate(test_x, split.test["label"].tolist())

            self._train_size = len(split.train)
            self._test_count = len(split.test)
            self._train_seconds = time.perf_counter() - start

            with tempfile.TemporaryDirectory() as tmp:
                model_path = os.path.join(tmp, "representations.joblib")
                self._suite.save(model_path)
                self._model_size_mb = os.path.getsize(model_path) / 1e6
                self._ready = True
                self._log_to_mlflow(model_path)
            return self._results

    def predict(self, text: str) -> Dict:
        """Everything the playground shows for one piece of text."""
        if not self._ready:
            self.train()
        clean = self._preprocessor.transform(text)
        return {
            "pipeline": self._preprocessor.trace(text),
            "tokens": self._tokens.analyze(text),
            "representations": self._suite.explain(clean),
        }

    def _comparison(self) -> Dict:
        """One entry per representation: test metrics plus vector statistics.
        Keys are the representation ids so About {{tokens}} can address them."""
        rows = {}
        for rep, name in REPRESENTATIONS.items():
            m = self._results[rep]["metrics"]
            st = self._suite.stats[rep]
            rows[rep] = {
                "name": name,
                "accuracy": f"{m['accuracy'] * 100:.1f}%",
                "f1": f"{m['f1']:.3f}",
                "roc_auc": f"{m['roc_auc']:.3f}",
                "vocabulary_size": f"{st['vocabulary_size']:,}",
                "density_pct": f"{st['density_pct']:.3f}%",
                "nonzeros_per_doc": st["nonzeros_per_doc"],
                "fit_seconds": f"{st['fit_seconds']:.1f}s",
            }
        return rows

    def get_model_info(self) -> Dict:
        """Model metadata for the About drawer and Model Card.

        DOES NOT trigger training — Cloudflare caps origin responses at 100s, so
        a metadata endpoint never trains (Phase 2a lesson). Before training it
        returns the static fields with empty metrics.
        """
        info = {
            "model_type": "LogisticRegression × 4",
            "architecture": ARCHITECTURE,
            "dataset": _DATASET,
            "target": "sentiment (Negative / Positive)",
            "parameters": {
                "min_df": MIN_DF,
                "ngram_max_features": NGRAM_MAX_FEATURES,
                "C": C,
                "solver": SOLVER,
            },
            "preprocessing": {"steps": self._preprocessor.step_names},
            "representations": REPRESENTATIONS,
            "metrics": {},
            "metrics_display": {},
            "comparison": None,
            "confusion_matrix": None,
            "split": None,
            "training": None,
            "run_id": None,
            "experiment_id": None,
            "mlflow_url": None,
        }
        if not self._ready:
            return info
        best = max(self._results, key=lambda r: self._results[r]["metrics"]["accuracy"])
        worst = min(self._results, key=lambda r: self._results[r]["metrics"]["accuracy"])
        tf = self._results["tfidf"]
        info.update({
            # Headline metrics are the TF-IDF model's (the lecture's end point).
            "metrics": {rep: r["metrics"] for rep, r in self._results.items()},
            "metrics_display": {
                "accuracy": f"{tf['metrics']['accuracy'] * 100:.1f}%",
                "precision": f"{tf['metrics']['precision']:.3f}",
                "recall": f"{tf['metrics']['recall']:.3f}",
                "f1": f"{tf['metrics']['f1']:.3f}",
                "roc_auc": f"{tf['metrics']['roc_auc']:.3f}",
                "best": REPRESENTATIONS[best],
                "spread": f"{(self._results[best]['metrics']['accuracy'] - self._results[worst]['metrics']['accuracy']) * 100:.1f} points",
                "transform_ms_per_doc": f"{tf['transform_ms_per_doc']:.2f} ms",
            },
            "comparison": self._comparison(),
            "confusion_matrix": {"labels": self._suite.labels, "matrix": tf["confusion_matrix"]},
            "split": {"train_samples": self._train_size, "test_samples": self._test_count},
            "training": {
                "seconds": f"{self._train_seconds:.1f}s",
                "model_size": f"{self._model_size_mb:.1f} MB",
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

    def _log_to_mlflow(self, model_path: str) -> None:
        """One parent run plus a nested child run per representation, so MLflow's
        compare view lines the four up. Classic `mlflow.log_artifact` path, NOT the
        LoggedModel API (Phase 2b.10 lesson, see mlflow_operational_lessons)."""
        try:
            import mlflow
            mlflow.set_tracking_uri(_MLFLOW_URI)
            mlflow.set_experiment(_EXPERIMENT)
            with mlflow.start_run() as run:
                mlflow.log_params({
                    "architecture": ARCHITECTURE,
                    "min_df": MIN_DF,
                    "ngram_max_features": NGRAM_MAX_FEATURES,
                    "C": C,
                    "solver": SOLVER,
                    "n_train": self._train_size,
                    "n_test": self._test_count,
                    "preprocessing": ",".join(self._preprocessor.step_names),
                    "dataset": _DATASET,
                })
                mlflow.log_metrics({
                    "train_seconds": round(self._train_seconds, 3),
                    "model_size_mb": round(self._model_size_mb, 2),
                    **{f"{rep}_accuracy": r["metrics"]["accuracy"] for rep, r in self._results.items()},
                })
                self._run_id = run.info.run_id
                self._experiment_id = str(run.info.experiment_id)
                for rep, name in REPRESENTATIONS.items():
                    with mlflow.start_run(run_name=rep, nested=True):
                        mlflow.log_params({"representation": name})
                        mlflow.log_metrics({
                            **self._results[rep]["metrics"],
                            **{k: v for k, v in self._suite.stats[rep].items()},
                        })
                try:
                    with tempfile.TemporaryDirectory() as tmp:
                        mlflow.log_artifact(model_path, artifact_path="model")
                        cm_path = os.path.join(tmp, "comparison.json")
                        with open(cm_path, "w") as f:
                            json.dump({"results": self._results, "stats": self._suite.stats}, f)
                        mlflow.log_artifact(cm_path, artifact_path="evaluation")
                except Exception as artifact_err:
                    logger.warning(f"MLflow artifact logging skipped: {artifact_err}")
        except Exception as e:
            logger.warning(f"MLflow logging skipped: {e}")
