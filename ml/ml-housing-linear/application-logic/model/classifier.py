from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from typing import Dict, List
import numpy as np


class HousingRegressor:
    def __init__(self):
        self._model = LinearRegression()
        self._trained = False

    def train(self, X_train, y_train) -> "HousingRegressor":
        self._model.fit(X_train, y_train)
        self._trained = True
        return self

    def predict(self, X) -> List[float]:
        self._check_trained()
        return self._model.predict(X).tolist()

    def evaluate(self, X_test, y_test) -> Dict:
        self._check_trained()
        y_pred = self._model.predict(X_test)
        return {
            "rmse": round(float(np.sqrt(mean_squared_error(y_test, y_pred))), 4),
            "mae":  round(float(mean_absolute_error(y_test, y_pred)), 4),
            "r2":   round(float(r2_score(y_test, y_pred)), 4),
        }

    def _check_trained(self):
        if not self._trained:
            raise RuntimeError("Model must be trained before calling predict or evaluate.")

    @property
    def is_trained(self) -> bool:
        return self._trained
