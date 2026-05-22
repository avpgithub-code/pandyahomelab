"""Tests for DB layer (loaders, repository)."""


def test_loaders_exist():
    """Test that loader modules can be imported."""
    from ...db_logic.loaders.loaders import BaseDataLoader, LocalDataLoader
    assert BaseDataLoader is not None
    assert LocalDataLoader is not None
