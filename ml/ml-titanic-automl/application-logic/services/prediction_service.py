import os
import logging
import pandas as pd
from typing import Dict, Optional

from db_logic.loaders.loaders import LocalDataLoader

logger = logging.getLogger(__name__)

_MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://ml-mlflow:5000")
_EXPERIMENT = "ml-titanic-automl"


class PredictionService:
    def __init__(self):
        self._loader = LocalDataLoader()
        self._model = None
        self._leaderboard = None
        self._best_model_name = None
        self._metrics: Dict = {}
        self._run_id: Optional[str] = None
        self._experiment_id: Optional[str] = None
        self._ready = False

    def train(self) -> Dict:
        from pycaret.classification import (
            setup, compare_models, tune_model,
            finalize_model, pull
        )
        import mlflow

        df = self._loader.load()

        mlflow.set_tracking_uri(_MLFLOW_URI)
        mlflow.set_experiment(_EXPERIMENT)

        # log_experiment=False, log_plots=False — avoids PyCaret deepcopying the
        # experiment object for MLflow serialization, which fails because
        # ThreadLocalVariable doesn't implement __copy__/__deepcopy__
        setup(
            data=df,
            target="survived",
            session_id=42,
            log_experiment=False,
            log_plots=False,
            verbose=False,
            html=False,
            n_jobs=1,
        )

        top_models = compare_models(n_select=5, sort="AUC", verbose=False)
        leaderboard_df = pull()
        self._leaderboard = leaderboard_df.head(5).to_dict(orient="records")

        tuned = tune_model(top_models[0], optimize="AUC", verbose=False)
        self._best_model_name = type(tuned).__name__

        self._model = finalize_model(tuned)

        best_row = leaderboard_df.iloc[0]
        self._metrics = {
            "accuracy":  round(float(best_row.get("Accuracy", 0)), 4),
            "auc":       round(float(best_row.get("AUC", 0)), 4),
            "f1":        round(float(best_row.get("F1", 0)), 4),
            "precision": round(float(best_row.get("Prec.", 0)), 4),
            "recall":    round(float(best_row.get("Recall", 0)), 4),
        }
        self._ready = True

        # Log to MLflow manually — safe, no deepcopy of experiment state
        try:
            with mlflow.start_run() as run:
                self._run_id = run.info.run_id
                self._experiment_id = str(run.info.experiment_id)
                mlflow.log_params({
                    "best_model": self._best_model_name,
                    "n_algorithms_compared": 5,
                    "optimized_for": "AUC",
                    "session_id": 42,
                })
                mlflow.log_metrics(self._metrics)
                mlflow.set_tag("dataset", "titanic")
                mlflow.set_tag("framework", "pycaret-3.3.1")
        except Exception as e:
            logger.warning(f"MLflow logging skipped: {e}")

        return self._metrics

    def predict(self, features: Dict) -> Dict:
        if not self._ready:
            self.train()

        X = pd.DataFrame([features])

        # Call sklearn Pipeline directly — avoids PyCaret's predict_model() which
        # requires thread-local experiment context that may not exist in this thread
        pred_label = int(self._model.predict(X)[0])

        if hasattr(self._model, "predict_proba"):
            proba = self._model.predict_proba(X)[0]
            score = round(float(max(proba)), 4)
        else:
            score = 1.0

        return {
            "prediction": pred_label,
            "survived": bool(pred_label),
            "survival_label": "Survived" if pred_label == 1 else "Did Not Survive",
            "confidence": score,
        }

    def get_model_info(self) -> Dict:
        if not self._ready:
            self.train()
        return {
            "model_type": "AutoML Classifier",
            "best_model": self._best_model_name,
            "dataset": "Titanic",
            "n_samples": 891,
            "n_features": 7,
            "algorithms_compared": 5,
            "optimized_for": "AUC",
            "leaderboard": self._leaderboard,
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
