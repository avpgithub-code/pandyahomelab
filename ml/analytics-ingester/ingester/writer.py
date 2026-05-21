"""Batch-insert enriched events into analytics.visitor_events."""
import logging
from typing import Dict, Any, List

import psycopg2
from psycopg2.extras import execute_batch

logger = logging.getLogger("ingester.writer")

INSERT_SQL = """
INSERT INTO analytics.visitor_events
    (occurred_at, ip_hash, country, method, path, status_code,
     bytes_sent, response_time_ms, referrer, user_agent, is_bot)
VALUES
    (%(occurred_at)s, %(ip_hash)s, %(country)s, %(method)s, %(path)s, %(status_code)s,
     %(bytes_sent)s, %(response_time_ms)s, %(referrer)s, %(user_agent)s, %(is_bot)s)
"""


class Writer:
    """Holds a persistent psycopg2 connection; reconnects on failure."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._conn = None

    def _connect(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.dsn)
            self._conn.set_session(autocommit=False)
        return self._conn

    def insert_batch(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                execute_batch(cur, INSERT_SQL, rows, page_size=200)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            self._conn = None  # force reconnect on next call
            raise

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()
        self._conn = None
