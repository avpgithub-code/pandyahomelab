"""Utility functions."""
import hashlib
from typing import Any


def hash_data(data: Any) -> str:
    """Generate hash of data for cache keys."""
    data_str = str(data).encode()
    return hashlib.md5(data_str).hexdigest()
