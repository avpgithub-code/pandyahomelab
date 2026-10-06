"""Read-only access to the serving DB, reopened when the pipeline swaps in a new file.

The pipeline never edits cricstat.sqlite in place: every build writes a new file and os.replace()s
it (F3 §8). So a connection is opened with immutable=1 (no locking, works on a read-only mount),
and each request compares the path's inode with the one it opened; a new inode means a new build,
and the connection is reopened. One connection per worker thread (sqlite3 objects are not shared).
"""
import os
import sqlite3
import threading
import time
from typing import Dict, List, Optional, Tuple

from shared.exceptions import BadFilter, NoData

QUERY_SECONDS = float(os.getenv("CRICSTAT_API_QUERY_SECONDS", "10"))


class QueryTimeout(Exception):
    """A query ran past QUERY_SECONDS and was interrupted (F5 §2: request time limits)."""


class ServingDB:
    def __init__(self, path: str):
        self.path = path
        self._local = threading.local()
        self._shared = {}                 # (inode, name) → value, shared by all threads
        self._lock = threading.Lock()

    def conn(self) -> sqlite3.Connection:
        try:
            ino = os.stat(self.path).st_ino
        except FileNotFoundError:
            raise NoData("no serving database yet (%s)" % os.path.basename(self.path)) from None
        c = getattr(self._local, "conn", None)
        if c is None or self._local.ino != ino:
            if c is not None:
                c.close()
            c = sqlite3.connect("file:%s?mode=ro&immutable=1" % self.path, uri=True,
                                check_same_thread=False)
            c.row_factory = sqlite3.Row
            local = self._local
            c.set_progress_handler(lambda: 1 if time.monotonic() > local.deadline else 0, 20000)
            self._local.conn, self._local.ino = c, ino
        return c

    def cached(self, name: str, factory):
        """A read-only value computed once per database file and shared by every thread; a new
        build (new inode) starts a fresh set. Values must never be mutated by callers."""
        self.conn()
        key = (self._local.ino, name)
        value = self._shared.get(key)
        if value is None:
            with self._lock:
                value = self._shared.get(key)
                if value is None:
                    value = factory()
                    stale = [k for k in self._shared if k[0] != key[0]]
                    for k in stale:
                        del self._shared[k]
                    self._shared[key] = value
        return value

    def _run(self, sql: str, args):
        c = self.conn()
        self._local.deadline = time.monotonic() + QUERY_SECONDS
        try:
            return c.execute(sql, args).fetchall()
        except sqlite3.OperationalError as exc:
            if "interrupted" in str(exc):
                raise QueryTimeout(sql[:80]) from exc
            raise

    def all(self, sql: str, args=()) -> List[dict]:
        return [dict(r) for r in self._run(sql, args)]

    def one(self, sql: str, args=()) -> Optional[dict]:
        rows = self._run(sql, args)
        return dict(rows[0]) if rows else None

    def scopes(self) -> "Scopes":
        return self.cached("scopes", lambda: Scopes(self))


class Scopes:
    """The scopes the marts are built for (F4 R21/R22), and SQL to select an atom's match in one.

    TEST / ODI / T20I / any other format key; a featured competition slug (e.g. ipl);
    LEAGUES = featured domestic leagues; ALL = official international formats + featured leagues.
    Mirrors db-logic/marts/marts.sql in cricstat-pipeline (a test checks they agree).
    """

    def __init__(self, db: ServingDB):
        self.formats: Dict[str, dict] = {r["format_key"]: r for r in db.all(
            "SELECT DISTINCT format_key, format_family, level FROM format_map")}
        self.featured: Dict[str, dict] = {}
        for r in db.all("SELECT competition_slug, event_name, gender FROM competitions"
                        " WHERE is_featured = 1 ORDER BY competition_key"):
            self.featured.setdefault(r["competition_slug"], r)

    def check(self, scope: str) -> str:
        if scope in ("ALL", "LEAGUES") or scope in self.formats or scope in self.featured:
            return scope
        raise BadFilter("unknown scope %r; use ALL, LEAGUES, one of %s, or a league slug (%s)"
                        % (scope, ", ".join(sorted(self.formats)),
                           ", ".join(sorted(self.featured))))

    def family(self, scope: str) -> Optional[str]:
        """Format family when the scope is a single format (or a T20 league slug)."""
        if scope in self.formats:
            return self.formats[scope]["format_family"]
        return None

    def clause(self, scope: str, alias: str) -> Tuple[str, list]:
        """SQL condition on `alias` (a table with format_key + competition_key)."""
        scope = self.check(scope)
        featured = ("%s.competition_key IN (SELECT competition_key FROM competitions"
                    " WHERE is_featured = 1)" % alias)
        domestic = ("%s.format_key IN (SELECT format_key FROM format_map WHERE level = 'domestic')"
                    % alias)
        if scope in self.formats:
            return "%s.format_key = ?" % alias, [scope]
        if scope == "LEAGUES":
            return "(%s AND %s)" % (featured, domestic), []
        if scope == "ALL":
            official = ("%s.format_key IN (SELECT format_key FROM format_map"
                        " WHERE level = 'international_official')" % alias)
            return "(%s OR (%s AND %s))" % (official, featured, domestic), []
        return ("%s.competition_key IN (SELECT competition_key FROM competitions"
                " WHERE competition_slug = ? AND is_featured = 1)" % alias, [scope])
