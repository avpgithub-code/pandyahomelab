"""Lightweight PostgreSQL connection helper using psycopg2 + RealDictCursor."""
import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL", "")


@contextmanager
def get_cursor():
    """Yield a RealDictCursor; close the connection when the block exits."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL env var required")
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
    finally:
        conn.close()
