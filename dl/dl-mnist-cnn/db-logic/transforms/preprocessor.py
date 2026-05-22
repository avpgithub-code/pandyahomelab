"""Inference-time preprocessing for MNIST canvas inputs.

The canvas drawing UI sends a flat list of 784 floats (0-255 range, row-major
28x28 image). This module converts that into a normalized 1x1x28x28 tensor
matching the statistics torchvision uses during training.

The training-side normalization (applied by torchvision.transforms.Normalize)
lives in db_logic.loaders.loaders — both paths read MEAN and STD from here so
the constants stay in one place.
"""
from typing import List

import torch


# Canonical MNIST dataset statistics — single source of truth for both the
# training pipeline (loader) and the inference pipeline (this module).
MEAN: float = 0.1307
STD: float = 0.3081

IMG_SIZE: int = 28
N_PIXELS: int = IMG_SIZE * IMG_SIZE


class DataPreprocessor:
    """Converts raw canvas pixel arrays into normalized 1x1x28x28 tensors."""

    @staticmethod
    def transform_input(pixels: List[float]) -> torch.Tensor:
        if len(pixels) != N_PIXELS:
            raise ValueError(f"Expected {N_PIXELS} pixels, got {len(pixels)}")
        t = torch.tensor(pixels, dtype=torch.float32).reshape(1, 1, IMG_SIZE, IMG_SIZE)
        return (t / 255.0 - MEAN) / STD
