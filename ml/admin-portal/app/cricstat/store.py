"""Postgres storage for the golden review (schema `cricstat`, created on startup, idempotent).

References and decisions are the owner's own work, so they live here (backed up with ml-postgres)
rather than in cricstat's rebuildable SQLite files. Export to CSV to keep a record in the repo.
"""
import json
from typing import Dict, List, Optional, Tuple

from app.db import get_cursor

SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS cricstat;

CREATE TABLE IF NOT EXISTS cricstat.golden_reference (
    entity_id     TEXT        NOT NULL,   -- player id (8 hex) or team "name|gender|type"
    scope         TEXT        NOT NULL,
    metric        TEXT        NOT NULL,
    reference     TEXT        NOT NULL,
    source        TEXT,
    checked_on    DATE,
    explanation   TEXT,
    ours_at_check TEXT,                   -- our figure when the reference was entered
    mat_at_check  TEXT,                   -- that block's Mat then; a later change → 'stale'
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (entity_id, scope, metric)
);

CREATE TABLE IF NOT EXISTS cricstat.golden_suggestion (
    entity_id  TEXT        NOT NULL,
    scope      TEXT        NOT NULL,
    metric     TEXT        NOT NULL,
    value      TEXT        NOT NULL,
    source_url TEXT,
    as_of      DATE,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (entity_id, scope, metric)
);

CREATE TABLE IF NOT EXISTS cricstat.golden_run (
    run_id      BIGSERIAL   PRIMARY KEY,
    kind        TEXT        NOT NULL CHECK (kind IN ('verify', 'check')),
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status      TEXT        NOT NULL,     -- running | success | error
    summary     JSONB,
    error       TEXT
);
"""
Key = Tuple[str, str, str]


def ensure_schema() -> None:
    with get_cursor() as cur:
        cur.execute(SCHEMA_SQL)
        cur.connection.commit()


def references() -> Dict[Key, dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM cricstat.golden_reference")
        return {(r["entity_id"], r["scope"], r["metric"]):
                dict(r, checked_on=r["checked_on"].isoformat() if r["checked_on"] else "")
                for r in cur.fetchall()}


def suggestions() -> Dict[Key, dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM cricstat.golden_suggestion")
        return {(r["entity_id"], r["scope"], r["metric"]):
                dict(r, as_of=r["as_of"].isoformat() if r["as_of"] else "")
                for r in cur.fetchall()}


def save_reference(key: Key, reference: str, source: str, checked_on: Optional[str],
                   explanation: str, ours: str, mat: str) -> None:
    """Upsert. A changed reference (or a cleared mat_at_check) re-snapshots ours and Mat."""
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO cricstat.golden_reference (entity_id, scope, metric, reference, source,"
            " checked_on, explanation, ours_at_check, mat_at_check)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (entity_id, scope, metric) DO UPDATE SET"
            "  source = EXCLUDED.source, checked_on = EXCLUDED.checked_on,"
            "  explanation = EXCLUDED.explanation, updated_at = NOW(),"
            "  ours_at_check = CASE WHEN cricstat.golden_reference.reference <> EXCLUDED.reference"
            "   THEN EXCLUDED.ours_at_check ELSE cricstat.golden_reference.ours_at_check END,"
            "  mat_at_check = CASE WHEN cricstat.golden_reference.reference <> EXCLUDED.reference"
            "   THEN EXCLUDED.mat_at_check ELSE cricstat.golden_reference.mat_at_check END,"
            "  reference = EXCLUDED.reference",
            key + (reference, source or None, checked_on or None, explanation or None, ours, mat))
        cur.connection.commit()


def delete_reference(key: Key) -> None:
    with get_cursor() as cur:
        cur.execute("DELETE FROM cricstat.golden_reference WHERE entity_id = %s AND scope = %s"
                    " AND metric = %s", key)
        cur.connection.commit()


def replace_suggestions(rows: List[dict]) -> None:
    with get_cursor() as cur:
        cur.execute("DELETE FROM cricstat.golden_suggestion")
        for r in rows:
            cur.execute("INSERT INTO cricstat.golden_suggestion (entity_id, scope, metric, value,"
                        " source_url, as_of) VALUES (%s, %s, %s, %s, %s, %s)",
                        (r["entity_id"], r["scope"], r["metric"], r["value"], r["source_url"],
                         r["as_of"]))
        cur.connection.commit()


def start_run(kind: str) -> Optional[int]:
    """Insert a 'running' row unless one of this kind started in the last 20 minutes."""
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM cricstat.golden_run WHERE kind = %s AND status = 'running'"
                    " AND started_at > NOW() - INTERVAL '20 minutes'", (kind,))
        if cur.fetchone():
            return None
        cur.execute("INSERT INTO cricstat.golden_run (kind, status) VALUES (%s, 'running')"
                    " RETURNING run_id", (kind,))
        run_id = cur.fetchone()["run_id"]
        cur.connection.commit()
        return run_id


def finish_run(run_id: int, status: str, summary: Optional[dict] = None,
               error: Optional[str] = None) -> None:
    with get_cursor() as cur:
        cur.execute("UPDATE cricstat.golden_run SET finished_at = NOW(), status = %s,"
                    " summary = %s, error = %s WHERE run_id = %s",
                    (status, json.dumps(summary) if summary is not None else None, error, run_id))
        cur.connection.commit()


def runs(limit: int = 10) -> List[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM cricstat.golden_run ORDER BY run_id DESC LIMIT %s", (limit,))
        return cur.fetchall()


def last_run(kind: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM cricstat.golden_run WHERE kind = %s ORDER BY run_id DESC"
                    " LIMIT 1", (kind,))
        return cur.fetchone()
