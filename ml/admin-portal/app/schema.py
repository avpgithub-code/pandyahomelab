"""Bootstrap the feedback tables in the analytics schema on startup. Idempotent.

The `analytics` schema itself is created by the analytics-ingester service, but
we include CREATE SCHEMA IF NOT EXISTS here for safety in case the admin-portal
ever starts before the ingester (e.g. in a clean redeploy).
"""
import psycopg2

FEEDBACK_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.feedback_likes (
    id          BIGSERIAL    PRIMARY KEY,
    page_id     VARCHAR(255) NOT NULL,
    ip_hash     CHAR(64)     NOT NULL,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_likes_page          ON analytics.feedback_likes (page_id);
CREATE INDEX IF NOT EXISTS idx_likes_ip_page_day   ON analytics.feedback_likes (ip_hash, page_id, created_at);

CREATE TABLE IF NOT EXISTS analytics.feedback_comments (
    id          BIGSERIAL    PRIMARY KEY,
    page_id     VARCHAR(255) NOT NULL,
    ip_hash     CHAR(64)     NOT NULL,
    name        VARCHAR(80),
    body        TEXT         NOT NULL,
    hidden      BOOLEAN      DEFAULT FALSE,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comments_page    ON analytics.feedback_comments (page_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_ip_hour ON analytics.feedback_comments (ip_hash, created_at);
"""


def ensure_feedback_schema(dsn: str) -> None:
    """Create the feedback tables + indexes if they don't exist. Safe to call repeatedly."""
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(FEEDBACK_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
