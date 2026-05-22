"""Data loader for MNIST handwritten digits (PyTorch CNN classifier).

Provides DataLoader objects for training and evaluation. torchvision auto-
downloads the dataset (~11MB) into data_dir on first call. Inference-time
preprocessing (canvas pixel list -> tensor) lives in db_logic.transforms.
"""
import os
from typing import List

from torch.utils.data import DataLoader
from torchvision import datasets, transforms

from db_logic.transforms.preprocessor import MEAN, STD


class LocalDataLoader:
    """Loads MNIST via torchvision (auto-downloads on first call)."""

    CLASSES: List[int] = list(range(10))
    IMG_SIZE: int = 28
    TRAIN_BATCH_SIZE: int = 64
    TEST_BATCH_SIZE: int = 1000

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), "../../data")
        self.data_dir = os.path.abspath(data_dir)
        self._transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((MEAN,), (STD,)),
        ])

    def load_train(self) -> DataLoader:
        dataset = datasets.MNIST(
            self.data_dir, train=True, download=True, transform=self._transform
        )
        return DataLoader(dataset, batch_size=self.TRAIN_BATCH_SIZE, shuffle=True)

    def load_test(self) -> DataLoader:
        dataset = datasets.MNIST(
            self.data_dir, train=False, download=True, transform=self._transform
        )
        return DataLoader(dataset, batch_size=self.TEST_BATCH_SIZE, shuffle=False)
