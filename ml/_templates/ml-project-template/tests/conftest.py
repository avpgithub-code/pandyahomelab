"""Pytest configuration and shared fixtures."""
import pytest


@pytest.fixture
def sample_data():
    """Sample data for testing."""
    return [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]


@pytest.fixture
def expected_prediction():
    """Expected prediction result."""
    return 0.5
