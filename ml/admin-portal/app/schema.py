"""Bootstrap the feedback + page-view tables in the analytics schema on startup. Idempotent.

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

-- One row per page load that actually ran our JS (the beacon in feedback-widget.js).
-- Bots that only fetch HTML never create a row, so this is the "real visitor" table.
--   pv_id     random per page load; later beacons for the same load UPDATE this row
--   visit_id  random per browser tab session (sessionStorage) — groups page views
--   engaged_ms  time the tab was visible AND the user was active (idle > 30 s stops the clock)
--   interacted  any scroll / click / key / touch — the strongest "a human was here" signal
CREATE TABLE IF NOT EXISTS analytics.page_views (
    pv_id            CHAR(16)     PRIMARY KEY,
    visit_id         CHAR(16)     NOT NULL,
    ip_hash          CHAR(64)     NOT NULL,
    country          CHAR(2),
    page_id          VARCHAR(255) NOT NULL,
    referrer_domain  VARCHAR(255),
    utm_source       VARCHAR(100),
    utm_medium       VARCHAR(100),
    utm_campaign     VARCHAR(100),
    device           VARCHAR(8),
    lang             VARCHAR(16),
    user_agent       TEXT,
    is_bot           BOOLEAN      DEFAULT FALSE,
    started_at       TIMESTAMPTZ  DEFAULT NOW(),
    last_seen_at     TIMESTAMPTZ  DEFAULT NOW(),
    engaged_ms       INTEGER      DEFAULT 0,
    max_scroll_pct   SMALLINT     DEFAULT 0,
    interactions     INTEGER      DEFAULT 0,
    interacted       BOOLEAN      DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_pv_started  ON analytics.page_views (started_at);
CREATE INDEX IF NOT EXISTS idx_pv_visit    ON analytics.page_views (visit_id);
CREATE INDEX IF NOT EXISTS idx_pv_ip_time  ON analytics.page_views (ip_hash, started_at);
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
