"""Pytest configuration — adds project root to sys.path so the symlinked
db_logic / application_logic / presentation_logic packages resolve without
needing PYTHONPATH=/app in the environment.

MLflow points at a closed local port with retries off, so every test exercises
the graceful-degradation path quickly instead of waiting on HTTP back-off.
"""
import os
import sys

os.environ["MLFLOW_TRACKING_URI"] = "http://127.0.0.1:9"
os.environ["MLFLOW_HTTP_REQUEST_MAX_RETRIES"] = "0"
os.environ["MLFLOW_HTTP_REQUEST_TIMEOUT"] = "2"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
