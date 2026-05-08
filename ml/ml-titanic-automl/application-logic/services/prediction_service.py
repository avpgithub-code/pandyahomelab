import os
import logging
import pandas as pd
from typing import Dict, List, Optional

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
            finalize_model, pull, predict_model
        )
        import mlflow

        df = self._loader.load()

        mlflow.set_tracking_uri(_MLFLOW_URI)

        setup(
            data=df,
            target="survived",
            session_id=42,
            log_experiment=True,
            experiment_name=_EXPERIMENT,
            log_plots=True,
            verbose=False,
            html=False,
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

        try:
            run = mlflow.last_active_run()
            if run:
                self._run_id = run.info.run_id
                self._experiment_id = str(run.info.experiment_id)
        except Exception as e:
            logger.warning(f"MLflow run_id capture skipped: {e}")

        return self._metrics

    def predict(self, features: Dict) -> Dict:
        if not self._ready:
            self.train()
        from pycaret.classification import predict_model
        X = pd.DataFrame([features])
        result = predict_model(self._model, data=X, verbose=False)
        pred = int(result["prediction_label"].iloc[0])
        score = round(float(result["prediction_score"].iloc[0]), 4)
        return {
            "prediction": pred,
            "survived": bool(pred),
            "survival_label": "Survived" if pred == 1 else "Did Not Survive",
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
