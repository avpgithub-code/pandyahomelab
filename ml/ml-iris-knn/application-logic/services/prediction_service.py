"""Prediction service: orchestrates data loading, preprocessing, and prediction."""
from typing import Dict, List

from db_logic.loaders.loaders import LocalDataLoader
from db_logic.transforms.preprocessor import DataPreprocessor
from application_logic.model.classifier import IrisClassifier


class PredictionService:
    """Handles end-to-end prediction requests for Iris classification."""

    def __init__(self):
        self._loader = LocalDataLoader()
        self._preprocessor = DataPreprocessor()
        self._classifier = IrisClassifier(n_neighbors=3)
        self._ready = False

    def train(self) -> Dict:
        df = self._loader.load()
        X_train, X_test, y_train, y_test = self._loader.split(df)
        X_train_scaled = self._preprocessor.fit_transform(X_train)
        X_test_scaled = self._preprocessor.transform(X_test)
        self._classifier.train(X_train_scaled, y_train)
        self._ready = True
        return self._classifier.evaluate(X_test_scaled, y_test)

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

    @property
    def is_ready(self) -> bool:
        return self._ready
