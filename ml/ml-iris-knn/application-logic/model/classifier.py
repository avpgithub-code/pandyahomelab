"""Iris k-NN classifier."""
from abc import ABC, abstractmethod
from typing import Dict, List

import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


class BaseClassifier(ABC):
    @abstractmethod
    def train(self, X_train, y_train):
        pass

    @abstractmethod
    def predict(self, X) -> List[int]:
        pass

    @abstractmethod
    def evaluate(self, X_test, y_test) -> Dict:
        pass


class IrisClassifier(BaseClassifier):
    """K-Nearest Neighbors classifier for Iris species prediction."""

    CLASSES = {0: "setosa", 1: "versicolor", 2: "virginica"}

    def __init__(self, n_neighbors: int = 3):
        self._model = KNeighborsClassifier(n_neighbors=n_neighbors, algorithm="ball_tree")
        self._trained = False

    def train(self, X_train, y_train) -> "IrisClassifier":
        self._model.fit(X_train, y_train)
        self._trained = True
        return self

    def predict(self, X) -> List[int]:
        self._check_trained()
        return self._model.predict(X).tolist()

    def predict_proba(self, X) -> List[List[float]]:
        self._check_trained()
        return self._model.predict_proba(X).tolist()

    def evaluate(self, X_test, y_test) -> Dict:
        self._check_trained()
        y_pred = self._model.predict(X_test)
        return {
            "accuracy":         round(float(accuracy_score(y_test, y_pred)), 4),
            "precision_macro":  round(float(precision_score(y_test, y_pred, average="macro")), 4),
            "recall_macro":     round(float(recall_score(y_test, y_pred, average="macro")), 4),
            "f1_macro":         round(float(f1_score(y_test, y_pred, average="macro")), 4),
        }

    @property
    def is_trained(self) -> bool:
        return self._trained

    def _check_trained(self):
        if not self._trained:
            raise RuntimeError("Classifier must be trained before calling predict.")
