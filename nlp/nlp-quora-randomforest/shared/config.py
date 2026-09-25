"""Configuration management.

NLP domain (Phase 3 gate G1): nlp-mlflow is the only domain service, so there is
no DATABASE_URL / MINIO_* / REDIS_URL here. Add them only when a demo needs one
and its slot in docs/NETWORK_CIDR_SUMMARY.md §5 is brought up.
"""
import os
from typing import Optional


class Config:
    """Application configuration."""

    def __init__(self):
        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        self.API_PORT = int(os.getenv("API_PORT", "8000"))
        self.API_HOST = os.getenv("API_HOST", "0.0.0.0")
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

        # GLUE QQP parquet files (make data). Mounted read-only in the container;
        # the dataset's licence keeps it out of the image.
        self.QQP_DATA_DIR = os.getenv("QQP_DATA_DIR", "/app/data/qqp")
        # Rows sampled from GLUE train / validation. Train is capped for the NAS
        # memory guardrail; 0 means "use every row".
        self.QQP_MAX_TRAIN_ROWS = int(os.getenv("QQP_MAX_TRAIN_ROWS", "100000")) or None
        self.QQP_MAX_TEST_ROWS = int(os.getenv("QQP_MAX_TEST_ROWS", "0")) or None

        # MLflow — internal URI for logging, public base for links in the UI
        self.MLFLOW_TRACKING_URI = os.getenv(
            "MLFLOW_TRACKING_URI", "http://nlp-mlflow:5000"
        )
        self.MLFLOW_PUBLIC_BASE_URL = os.getenv(
            "MLFLOW_PUBLIC_BASE_URL", "https://mlflow-nlp.pandyahomelab.com"
        )


_config: Optional[Config] = None


def get_config() -> Config:
    """Get singleton config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
