"""Configuration from environment variables.

Paths default relative to CRICSTAT_HOME (the cricstat/ folder on the NAS host, /cricstat in the
image), like cricstat-pipeline, so the same settings work in both places.
"""
import os

_DEFAULT_HOME = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ATTRIBUTION = ("Match data from Cricsheet (cricsheet.org), used under the Open Data Commons "
               "Attribution License 1.0.")
COVERAGE = ("Cricsheet ball-by-ball, 2001–present (sparser before about 2005 for men and 2016 for "
            "women); Afghanistan men's matches not included")


class Config:
    def __init__(self):
        self.HOME = os.path.abspath(os.getenv("CRICSTAT_HOME", _DEFAULT_HOME))
        self.SERVING_DB = self._path("CRICSTAT_SERVING_DB", "data/db/cricstat.sqlite")
        self.RAW_DB = self._path("CRICSTAT_RAW_DB", "data/db/raw.sqlite")
        self.LOG_DIR = self._path("CRICSTAT_LOG_DIR", "logs")
        self.GOLDEN_SELECTION = self._path("CRICSTAT_GOLDEN_SELECTION",
                                           "docs/validation/golden-selection.csv")
        self.NAS_UTC_OFFSET = float(os.getenv("CRICSTAT_NAS_UTC_OFFSET", "-5"))
        self.LOG_LEVEL = os.getenv("CRICSTAT_LOG_LEVEL", "INFO").upper()
        self.CACHE_MAX_AGE = int(os.getenv("CRICSTAT_API_CACHE_MAX_AGE", "300"))
        self.CACHE_SWR = int(os.getenv("CRICSTAT_API_CACHE_SWR", "3600"))
        # P0.6 server-rendered page heads: the static shells (cricstat/web, mounted read-only in
        # the container), the public site and prefix for canonical URLs, and the bar a player or
        # team page must clear to be indexed (thinner pages get noindex but stay usable).
        self.WEB_DIR = self._path("CRICSTAT_WEB_DIR", "web")
        self.SITE_URL = os.getenv("CRICSTAT_SITE_URL", "https://pandyahomelab.com")
        self.PUBLIC_PREFIX = os.getenv("CRICSTAT_PUBLIC_PREFIX", "/cricket")
        self.INDEX_MIN_INTL = int(os.getenv("CRICSTAT_INDEX_MIN_INTL", "10"))
        self.INDEX_MIN_LEAGUE = int(os.getenv("CRICSTAT_INDEX_MIN_LEAGUE", "20"))

    def _path(self, name, default):
        value = os.getenv(name, default)
        return value if os.path.isabs(value) else os.path.join(self.HOME, value)
