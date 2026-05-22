"""Data loaders: load from local filesystem, S3, or database."""
from abc import ABC, abstractmethod


class BaseDataLoader(ABC):
    """Abstract base class for data loaders."""

    @abstractmethod
    def load(self):
        """Load data."""
        pass


class LocalDataLoader(BaseDataLoader):
    """Load data from local filesystem."""

    def __init__(self, path):
        self.path = path

    def load(self):
        """Load CSV or Parquet from disk."""
        pass


class S3DataLoader(BaseDataLoader):
    """Load data from MinIO/S3."""

    def __init__(self, bucket, key):
        self.bucket = bucket
        self.key = key

    def load(self):
        """Load from MinIO."""
        pass


class DatabaseDataLoader(BaseDataLoader):
    """Load data from PostgreSQL."""

    def __init__(self, query):
        self.query = query

    def load(self):
        """Load from database."""
        pass
