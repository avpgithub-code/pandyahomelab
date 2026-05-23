"""MNIST CNN classifier — PyTorch model + thin training/prediction wrapper.

Architecture: two conv layers + max-pool + two fully-connected layers.
Trained with Adam (lr=1e-3) + cross-entropy loss; targets >=98% test accuracy
in 3 epochs on the full 60k training set (~8 min on NAS CPU).
"""
from typing import Dict, List

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader


# Hyperparameters surfaced as module constants so PredictionService can log
# the same values to MLflow without re-defining them.
LEARNING_RATE = 1e-3
DEFAULT_EPOCHS = 3
ARCHITECTURE = "MnistCNN(conv1=1->32, conv2=32->64, fc1=9216->128, fc2=128->10)"


class MnistCNN(nn.Module):
    """2-conv + 2-FC CNN for 28x28 grayscale digit classification.

    Forward shape: (B, 1, 28, 28) -> conv1 (B, 32, 26, 26) -> conv2
    (B, 64, 24, 24) -> max_pool (B, 64, 12, 12) -> flatten (B, 9216)
    -> fc1 (B, 128) -> fc2 (B, 10) logits.
    """

    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, stride=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, stride=1)
        self.dropout1 = nn.Dropout(0.25)
        self.dropout2 = nn.Dropout(0.5)
        self.fc1 = nn.Linear(9216, 128)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.max_pool2d(x, 2)
        x = self.dropout1(x)
        x = torch.flatten(x, 1)
        x = F.relu(self.fc1(x))
        x = self.dropout2(x)
        return self.fc2(x)


class DigitClassifier:
    """Train/evaluate/predict wrapper around MnistCNN.

    Mirrors the shape of ml-iris-knn's IrisClassifier (is_trained property,
    runtime error if predict is called before train) so the PredictionService
    pattern carries over cleanly.
    """

    CLASSES: List[str] = [str(i) for i in range(10)]

    def __init__(self):
        self._model = MnistCNN()
        self._trained = False

    def train(self, train_loader: DataLoader, epochs: int = DEFAULT_EPOCHS) -> "DigitClassifier":
        optimizer = torch.optim.Adam(self._model.parameters(), lr=LEARNING_RATE)
        criterion = nn.CrossEntropyLoss()
        self._model.train()
        for _ in range(epochs):
            for data, target in train_loader:
                optimizer.zero_grad()
                loss = criterion(self._model(data), target)
                loss.backward()
                optimizer.step()
        self._trained = True
        return self

    def evaluate(self, test_loader: DataLoader) -> Dict:
        self._check_trained()
        self._model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for data, target in test_loader:
                pred = self._model(data).argmax(dim=1)
                correct += pred.eq(target).sum().item()
                total += len(target)
        return {
            "accuracy": round(correct / total, 4) if total else 0.0,
            "correct": correct,
            "total": total,
        }

    def predict(self, tensor: torch.Tensor) -> Dict:
        self._check_trained()
        self._model.eval()
        with torch.no_grad():
            output = self._model(tensor)
            probs = torch.softmax(output, dim=1)[0]
            pred = int(probs.argmax().item())
        return {
            "prediction": pred,
            "digit": str(pred),
            "confidence": round(float(probs[pred].item()), 4),
            "probabilities": {
                str(i): round(float(probs[i].item()), 4) for i in range(10)
            },
        }

    @property
    def is_trained(self) -> bool:
        return self._trained

    def _check_trained(self):
        if not self._trained:
            raise RuntimeError("Classifier must be trained before calling predict.")
