"""Read-only MediaWiki API client: page wikitext + revision id, with a polite pace and a disk cache.

Wikimedia asks for a descriptive User-Agent with contact details and no parallel hammering:
one request at a time, CRICSTAT_WIKI_PAUSE seconds apart. Every page is cached as JSON
(title, revid, fetched_at, wikitext) so the source revision of each supplement row is recorded
and re-runs during development don't refetch.
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Iterable, List, Optional

from shared.exceptions import SourceError
from shared.logger import get_logger

log = get_logger("wikipedia")


class WikiPage(dict):
    """{'title', 'revid', 'fetched_at', 'wikitext'}; 'missing': True when the page doesn't exist."""


class WikipediaClient:
    def __init__(self, cfg, cache_dir: Optional[str] = None, max_age_s: Optional[float] = None):
        self.cfg = cfg
        self.cache_dir = cache_dir or cfg.WIKI_CACHE_DIR
        self.max_age_s = max_age_s          # None = cache never expires (dev); 0 = always refetch
        self._last = 0.0

    # -- HTTP -------------------------------------------------------------------------------
    def _get(self, params: Dict[str, str]) -> dict:
        query = dict(params, format="json", formatversion="2")
        url = "%s?%s" % (self.cfg.WIKIPEDIA_API, urllib.parse.urlencode(query))
        req = urllib.request.Request(url, headers={"User-Agent": self.cfg.WIKIMEDIA_USER_AGENT})
        err = None
        for attempt in range(self.cfg.HTTP_RETRIES + 1):
            wait = self.cfg.WIKI_PAUSE - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            try:
                with urllib.request.urlopen(req, timeout=self.cfg.HTTP_TIMEOUT) as resp:
                    self._last = time.time()
                    return json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, OSError, ValueError) as exc:
                self._last = time.time()
                err = exc
                log.warning("wikipedia request failed (attempt %d): %s", attempt + 1, exc)
                time.sleep(self.cfg.HTTP_BACKOFF * (attempt + 1))
        raise SourceError("wikipedia request failed after retries: %s" % err)

    # -- cache ------------------------------------------------------------------------------
    def _cache_path(self, title: str) -> str:
        h = hashlib.sha1(title.encode("utf-8")).hexdigest()[:16]
        return os.path.join(self.cache_dir, "%s.json" % h)

    def _cached(self, title: str) -> Optional[WikiPage]:
        path = self._cache_path(title)
        if self.max_age_s == 0 or not os.path.exists(path):
            return None
        if self.max_age_s is not None and time.time() - os.path.getmtime(path) > self.max_age_s:
            return None
        with open(path, encoding="utf-8") as f:
            return WikiPage(json.load(f))

    def _store(self, page: WikiPage) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)
        path = self._cache_path(page["title"])
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(page, f, ensure_ascii=False)
        os.replace(tmp, path)

    # -- API --------------------------------------------------------------------------------
    def page(self, title: str) -> WikiPage:
        """Wikitext and revision id of one page (redirects followed)."""
        hit = self._cached(title)
        if hit is not None:
            return hit
        data = self._get({"action": "parse", "page": title, "prop": "wikitext|revid",
                          "redirects": "1"})
        if "error" in data:
            if data["error"].get("code") == "missingtitle":
                page = WikiPage(title=title, revid=None, fetched_at=_now(), wikitext="",
                                missing=True)
            else:
                raise SourceError("wikipedia error for %r: %s" % (title, data["error"]))
        else:
            p = data["parse"]
            page = WikiPage(title=title, resolved_title=p.get("title", title),
                            revid=p.get("revid"), fetched_at=_now(), wikitext=p["wikitext"])
        self._store(page)
        return page

    def search_title(self, query: str, must=(), never=(" A cricket", "women", "Under-19")
                     ) -> Optional[str]:
        """Best article title for a full-text search whose title contains every word in `must`
        (case-insensitive). Used only to find the second-source article for a row whose season
        section links none."""
        data = self._get({"action": "query", "list": "search", "srsearch": query,
                          "srlimit": "10", "srnamespace": "0"})
        for hit in data.get("query", {}).get("search", []):
            title = hit["title"]
            if all(w.lower() in title.lower() for w in must) and \
                    not any(w.lower() in title.lower() for w in never):
                return title
        return None

    def pages(self, titles: Iterable[str]) -> List[WikiPage]:
        return [self.page(t) for t in titles]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
