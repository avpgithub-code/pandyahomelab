from typing import Dict, List
import pandas as pd

from db_logic.loaders.loaders import LocalDataLoader
from db_logic.transforms.preprocessor import DataPreprocessor
from application_logic.model.classifier import HousingRegressor


class PredictionService:
    """Trains HousingRegressor on startup and serves predictions."""

    def __init__(self):
        self._loader = LocalDataLoader()
        self._preprocessor = DataPreprocessor()
        self._regressor = HousingRegressor()
        self._metrics: Dict = {}
        self._ready = False

    def train(self) -> Dict:
        df = self._loader.load()
        X_train, X_test, y_train, y_test = self._loader.split(df)
        X_train_scaled = self._preprocessor.fit_transform(X_train)
        X_test_scaled = self._preprocessor.transform(X_test)
        self._regressor.train(X_train_scaled, y_train)
        self._metrics = self._regressor.evaluate(X_test_scaled, y_test)
        self._ready = True
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

    @property
    def is_ready(self) -> bool:
        return self._ready
