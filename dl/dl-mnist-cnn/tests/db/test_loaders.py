"""Tests for DB logic layer — MNIST loader and inference-time preprocessor."""
import pytest
import torch
from torch.utils.data import DataLoader

from db_logic.loaders.loaders import LocalDataLoader
from db_logic.transforms.preprocessor import (
    DataPreprocessor,
    MEAN,
    STD,
    IMG_SIZE,
    N_PIXELS,
)


@pytest.fixture(scope="module")
def loader():
    return LocalDataLoader()


@pytest.fixture(scope="module")
def train_loader(loader):
    # Downloads ~11MB MNIST archive on first call; cached for the rest of the session.
    return loader.load_train()


@pytest.fixture(scope="module")
def test_loader(loader):
    return loader.load_test()


class TestLocalDataLoader:
    def test_classes_are_0_to_9(self, loader):
        assert loader.CLASSES == list(range(10))
        assert len(loader.CLASSES) == 10

    def test_image_size_is_28(self, loader):
        assert loader.IMG_SIZE == 28

    def test_load_train_returns_dataloader(self, train_loader):
        assert isinstance(train_loader, DataLoader)

    def test_load_test_returns_dataloader(self, test_loader):
        assert isinstance(test_loader, DataLoader)

    def test_train_dataset_size(self, train_loader):
        assert len(train_loader.dataset) == 60_000

    def test_test_dataset_size(self, test_loader):
        assert len(test_loader.dataset) == 10_000

    def test_train_batch_shape(self, train_loader):
        batch_x, batch_y = next(iter(train_loader))
        assert batch_x.shape == (LocalDataLoader.TRAIN_BATCH_SIZE, 1, 28, 28)
        assert batch_y.shape == (LocalDataLoader.TRAIN_BATCH_SIZE,)

    def test_train_batch_normalized(self, train_loader):
        # After Normalize, a typical batch should have values roughly centered
        # around 0 — not strictly so for any single batch, but mean and std
        # of the full dataset should land near 0 and 1 respectively.
        batch_x, _ = next(iter(train_loader))
        assert batch_x.dtype == torch.float32
        assert batch_x.min() >= (0.0 - MEAN) / STD - 0.01     # numerical floor
        assert batch_x.max() <= (1.0 - MEAN) / STD + 0.01     # numerical ceiling


class TestDataPreprocessor:
    def test_transform_input_shape(self):
        t = DataPreprocessor.transform_input([0.0] * N_PIXELS)
        assert t.shape == (1, 1, IMG_SIZE, IMG_SIZE)

    def test_transform_input_dtype_is_float32(self):
        t = DataPreprocessor.transform_input([0.0] * N_PIXELS)
        assert t.dtype == torch.float32

    def test_transform_input_zero_pixels(self):
        # All-zero input: every value normalizes to (0 - MEAN) / STD.
        t = DataPreprocessor.transform_input([0.0] * N_PIXELS)
        expected = -MEAN / STD
        assert torch.allclose(t, torch.full_like(t, expected))

    def test_transform_input_max_pixels(self):
        # All-255 input: every value normalizes to (1.0 - MEAN) / STD.
        t = DataPreprocessor.transform_input([255.0] * N_PIXELS)
        expected = (1.0 - MEAN) / STD
        assert torch.allclose(t, torch.full_like(t, expected))

    def test_transform_input_wrong_length_raises(self):
        with pytest.raises(ValueError, match="Expected"):
            DataPreprocessor.transform_input([0.0] * 100)

    def test_transform_input_empty_raises(self):
        with pytest.raises(ValueError, match="Expected"):
            DataPreprocessor.transform_input([])
