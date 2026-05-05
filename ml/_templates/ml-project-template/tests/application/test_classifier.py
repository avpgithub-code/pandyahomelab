"""Tests for application layer (model, services)."""


def test_classifier_exists():
    """Test that classifier module can be imported."""
    from ...application_logic.model.classifier import BaseClassifier
    assert BaseClassifier is not None
