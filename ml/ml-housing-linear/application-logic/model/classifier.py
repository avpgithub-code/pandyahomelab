"""Model architecture and training."""
from abc import ABC, abstractmethod


class BaseClassifier(ABC):
    """Abstract base class for classifiers."""

    @abstractmethod
    def train(self, X_train, y_train):
        """Train the model."""
        pass

    @abstractmethod
    def predict(self, X):
        """Make predictions."""
        pass

    @abstractmethod
    def evaluate(self, X_test, y_test):
        """Evaluate model performance."""
        pass
