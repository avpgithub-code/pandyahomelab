"""Custom exceptions."""


class MLProjectError(Exception):
    """Base exception for ML project."""
    pass


class DataLoadError(MLProjectError):
    """Error loading data."""
    pass


class ModelError(MLProjectError):
    """Error with model."""
    pass


class PredictionError(MLProjectError):
    """Error during prediction."""
    pass


class ConfigurationError(MLProjectError):
    """Error with configuration."""
    pass
