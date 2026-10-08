"""Configuration from environment variables.

Same convention as cricstat-pipeline: every path default is relative to the cricstat project root
(CRICSTAT_HOME, by default the folder that contains cricstat-models/), so the same settings work
on the NAS host and in a container (CRICSTAT_HOME=/cricstat).
"""
import os
from typing import Optional

_DEFAULT_HOME = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_MODELS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WIKIMEDIA_USER_AGENT = ("cricstat/0.1 (https://pandyahomelab.com/cricket/;"
                        " privacy@pandyahomelab.com) python-urllib")
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"


def _int(name, default):
    return int(os.getenv(name, str(default)))


def _float(name, default):
    return float(os.getenv(name, str(default)))


class Config:
    """Models configuration, read once from the environment."""

    def __init__(self):
        self.HOME = os.path.abspath(os.getenv("CRICSTAT_HOME", _DEFAULT_HOME))
        self.DATA_DIR = self._path("CRICSTAT_DATA_DIR", "data")
        self.SERVING_DB = self._path("CRICSTAT_SERVING_DB",
                                     os.path.join(self.DATA_DIR, "db", "cricstat.sqlite"))
        self.FORECAST_DB = self._path("CRICSTAT_FORECAST_DB",
                                      os.path.join(self.DATA_DIR, "db", "forecast.sqlite"))
        self.VENUE_MAP = self._path("CRICSTAT_VENUE_MAP", os.path.join("sql", "venue_map.csv"))
        # Reviewed inputs that ship inside the models image (not cricstat/sql/: no pipeline
        # publish).
        self.SUPPLEMENT_DIR = os.getenv("CRICSTAT_SUPPLEMENT_DIR",
                                        os.path.join(_MODELS_DIR, "supplement"))
        self.TOURNAMENTS_DIR = os.getenv("CRICSTAT_TOURNAMENTS_DIR",
                                         os.path.join(_MODELS_DIR, "tournaments"))
        self.WIKI_CACHE_DIR = self._path("CRICSTAT_WIKI_CACHE_DIR",
                                         os.path.join(self.DATA_DIR, "models", "wiki-cache"))
        self.LOG_DIR = self._path("CRICSTAT_LOG_DIR", "logs")
        self.LOG_LEVEL = os.getenv("CRICSTAT_LOG_LEVEL", "INFO").upper()

        self.WIKIMEDIA_USER_AGENT = os.getenv("CRICSTAT_WIKIMEDIA_USER_AGENT", WIKIMEDIA_USER_AGENT)
        self.WIKIPEDIA_API = os.getenv("CRICSTAT_WIKIPEDIA_API", WIKIPEDIA_API)
        self.WIKI_PAUSE = _float("CRICSTAT_WIKI_PAUSE", 1.0)            # seconds between requests
        # Jobs re-read pages older than this; development scripts may pass max_age_s=None.
        self.WIKI_CACHE_MAX_AGE_S = _float("CRICSTAT_WIKI_CACHE_MAX_AGE_S", 86400)
        # ML-domain tracker: the host reaches it on 127.0.0.1:5000, containers as ml-mlflow:5000.
        self.MLFLOW_URI = os.getenv("CRICSTAT_MLFLOW_URI", "http://127.0.0.1:5000")
        self.FULL_MEMBERS = os.getenv("CRICSTAT_FULL_MEMBERS",
                                      os.path.join(_MODELS_DIR, "ratings", "icc_full_members.csv"))
        self.REPORT_DIR = self._path("CRICSTAT_MODELS_REPORT_DIR",
                                     os.path.join(self.DATA_DIR, "models", "reports"))
        self.HTTP_TIMEOUT = _float("CRICSTAT_HTTP_TIMEOUT", 60)
        self.HTTP_RETRIES = _int("CRICSTAT_HTTP_RETRIES", 4)
        self.HTTP_BACKOFF = _float("CRICSTAT_HTTP_BACKOFF", 5)

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
