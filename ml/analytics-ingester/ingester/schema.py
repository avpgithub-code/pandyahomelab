"""Bootstrap the analytics schema + table + indexes on startup. Idempotent."""
import psycopg2

SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.visitor_events (
    id                BIGSERIAL    PRIMARY KEY,
    occurred_at       TIMESTAMPTZ  NOT NULL,
    ip_hash           CHAR(64)     NOT NULL,
    country           CHAR(2),
    method            VARCHAR(8)   NOT NULL,
    path              TEXT         NOT NULL,
    status_code       SMALLINT     NOT NULL,
    bytes_sent        INTEGER,
    response_time_ms  INTEGER,
    referrer          TEXT,
    user_agent        TEXT,
    is_bot            BOOLEAN      DEFAULT FALSE,
    created_at        TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ve_occurred_at ON analytics.visitor_events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_ve_ip_hash    ON analytics.visitor_events (ip_hash, occurred_at);
CREATE INDEX IF NOT EXISTS idx_ve_path       ON analytics.visitor_events (path, occurred_at);
CREATE INDEX IF NOT EXISTS idx_ve_country    ON analytics.visitor_events (country, occurred_at)
    WHERE country IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ve_not_bot    ON analytics.visitor_events (occurred_at)
    WHERE NOT is_bot;
"""


def ensure_schema(dsn: str) -> None:
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
