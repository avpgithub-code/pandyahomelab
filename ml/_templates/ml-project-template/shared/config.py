"""Configuration management."""
import os
from typing import Optional


class Config:
    """Application configuration."""

    def __init__(self):
        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        self.API_PORT = int(os.getenv("API_PORT", "8000"))
        self.API_HOST = os.getenv("API_HOST", "0.0.0.0")
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

        # Database
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL", "postgresql://postgres:password@localhost/db"
        )

        # MinIO
        self.MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.MINIO_BUCKET = os.getenv("MINIO_BUCKET", "ml-artifacts")

        # Redis
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

        # MLflow
        self.MLFLOW_TRACKING_URI = os.getenv(
            "MLFLOW_TRACKING_URI", "http://localhost:5000"
        )


_config: Optional[Config] = None


def get_config() -> Config:
    """Get singleton config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
