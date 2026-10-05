"""Configuration from environment variables.

Every path default is relative to the cricstat project root (CRICSTAT_HOME, by default
the folder that contains cricstat-pipeline/). A relative value in an env var is resolved
against CRICSTAT_HOME too, so the same settings work on the NAS host and in a container
(where CRICSTAT_HOME=/cricstat). No absolute NAS paths live here.
"""
import os
from typing import Optional

_DEFAULT_HOME = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FULL_URL = "https://cricsheet.org/downloads/all_json.zip"
RECENT_URL = "https://cricsheet.org/downloads/recently_added_7_json.zip"
USER_AGENT = "cricstat/0.1 (+https://pandyahomelab.com/cricket/)"


def _int(name, default):
    return int(os.getenv(name, str(default)))


def _float(name, default):
    return float(os.getenv(name, str(default)))


class Config:
    """Pipeline configuration, read once from the environment."""

    def __init__(self):
        self.HOME = os.path.abspath(os.getenv("CRICSTAT_HOME", _DEFAULT_HOME))
        self.DATA_DIR = self._path("CRICSTAT_DATA_DIR", "data")
        self.RAW_ZIP_DIR = self._path("CRICSTAT_RAW_ZIP_DIR", os.path.join(self.DATA_DIR, "raw"))
        self.RAW_DB = self._path("CRICSTAT_RAW_DB", os.path.join(self.DATA_DIR, "db", "raw.sqlite"))
        self.LOG_DIR = self._path("CRICSTAT_LOG_DIR", "logs")
        self.LOG_LEVEL = os.getenv("CRICSTAT_LOG_LEVEL", "INFO").upper()

        self.FULL_URL = os.getenv("CRICSTAT_FULL_URL", FULL_URL)
        self.RECENT_URL = os.getenv("CRICSTAT_RECENT_URL", RECENT_URL)
        self.USER_AGENT = os.getenv("CRICSTAT_USER_AGENT", USER_AGENT)
        self.HTTP_TIMEOUT = _float("CRICSTAT_HTTP_TIMEOUT", 60)
        self.HTTP_RETRIES = _int("CRICSTAT_HTTP_RETRIES", 4)
        self.HTTP_BACKOFF = _float("CRICSTAT_HTTP_BACKOFF", 5)

        self.KEEP_FULL_ZIPS = _int("CRICSTAT_KEEP_FULL_ZIPS", 3)
        self.KEEP_RECENT_ZIPS = _int("CRICSTAT_KEEP_RECENT_ZIPS", 7)

        # Data-quality gates (see application-logic/quality/gates.py)
        self.MAX_FAILED_ABS = _int("CRICSTAT_MAX_FAILED_ABS", 5)
        self.MAX_FAILED_FRAC = _float("CRICSTAT_MAX_FAILED_FRAC", 0.005)
        self.MAX_ACTIVE_DROP_FRAC = _float("CRICSTAT_MAX_ACTIVE_DROP_FRAC", 0.02)

    def _path(self, name, default):
        value = os.getenv(name, default)
        return value if os.path.isabs(value) else os.path.join(self.HOME, value)


_config: Optional[Config] = None


def get_config(reload: bool = False) -> Config:
    """Get the singleton config (reload=True re-reads the environment, for tests)."""
    global _config
    if _config is None or reload:
        _config = Config()
    return _config
