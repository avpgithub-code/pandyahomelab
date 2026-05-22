"""Pytest configuration — adds project root to sys.path so the symlinked
db_logic / application_logic / presentation_logic packages resolve without
needing PYTHONPATH=/app in the environment."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
