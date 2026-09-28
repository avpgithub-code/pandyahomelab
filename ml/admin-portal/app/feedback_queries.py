"""SQL for the feedback feature — likes, comments, rate-limit checks."""
from typing import Optional

from app.db import get_cursor


# INSERT-with-NOT-EXISTS = a tiny rate limiter at the DB layer.
# If the visitor already liked this page within the last day, RETURNING is empty.
LIKE_INSERT_SQL = """
INSERT INTO analytics.feedback_likes (page_id, ip_hash)
SELECT %(page_id)s, %(ip_hash)s
WHERE NOT EXISTS (
    SELECT 1 FROM analytics.feedback_likes
    WHERE page_id    = %(page_id)s
      AND ip_hash    = %(ip_hash)s
      AND created_at > NOW() - INTERVAL '1 day'
)
RETURNING id
"""

LIKE_COUNT_SQL = """
SELECT count(*) AS total
FROM analytics.feedback_likes
WHERE page_id = %s
"""

COMMENT_RATE_CHECK_SQL = """
SELECT count(*) AS recent
FROM analytics.feedback_comments
WHERE ip_hash    = %s
  AND page_id    = %s
  AND created_at > NOW() - INTERVAL '5 minutes'
"""

COMMENT_RATE_LIMIT_PER_WINDOW = 3

COMMENT_INSERT_SQL = """
INSERT INTO analytics.feedback_comments (page_id, ip_hash, name, body)
VALUES (%(page_id)s, %(ip_hash)s, %(name)s, %(body)s)
RETURNING id
"""


def insert_like(page_id: str, ip_hash: str) -> bool:
    """Insert a like; return True if it was new, False if rate-limited (silent dedup)."""
    with get_cursor() as cur:
        cur.execute(LIKE_INSERT_SQL, {"page_id": page_id, "ip_hash": ip_hash})
        row = cur.fetchone()
        cur.connection.commit()
        return row is not None


def count_likes(page_id: str) -> int:
    with get_cursor() as cur:
        cur.execute(LIKE_COUNT_SQL, (page_id,))
        return int(cur.fetchone()["total"])


def can_comment(ip_hash: str, page_id: str) -> bool:
    """True if this IP has made fewer than 3 comments on this page in the last 5 minutes."""
    with get_cursor() as cur:
        cur.execute(COMMENT_RATE_CHECK_SQL, (ip_hash, page_id))
        return int(cur.fetchone()["recent"]) < COMMENT_RATE_LIMIT_PER_WINDOW


def insert_comment(page_id: str, ip_hash: str, name: Optional[str], body: str) -> int:
    with get_cursor() as cur:
        cur.execute(COMMENT_INSERT_SQL, {
            "page_id": page_id,
            "ip_hash": ip_hash,
            "name":    name,
            "body":    body,
        })
        row = cur.fetchone()
        cur.connection.commit()
        return int(row["id"])


# ───────────────────── Admin moderation queries ────────────────────────

# Where a comment or like came from: the same visitor's page view (same IP hash) that was
# open when they sent it — preferably on the same page — and how that visit started.
# Nothing extra is collected; it only joins the feedback to page_views. Empty for
# feedback sent before the beacon existed (2026-09-27) or older than 13 months.
_CONTEXT_JOIN = """
LEFT JOIN LATERAL (
    SELECT pv.visit_id, pv.country, pv.device
    FROM analytics.page_views pv
    WHERE pv.ip_hash = f.ip_hash
      AND pv.started_at BETWEEN f.created_at - INTERVAL '6 hours' AND f.created_at + INTERVAL '1 minute'
    ORDER BY (pv.page_id = f.page_id) DESC, pv.started_at DESC
    LIMIT 1
) v ON TRUE
LEFT JOIN LATERAL (
    SELECT CASE
        WHEN l.utm_source IS NOT NULL THEN l.utm_source || ' (utm)'
        WHEN l.referrer_domain IS NULL THEN 'direct'
        WHEN l.referrer_domain = 'pandyahomelab.com' OR l.referrer_domain LIKE '%%.pandyahomelab.com' THEN 'internal'
        ELSE l.referrer_domain
    END AS source
    FROM analytics.page_views l
    WHERE l.visit_id = v.visit_id
    ORDER BY l.started_at
    LIMIT 1
) src ON TRUE
"""

_PAGE_FILTER = "(%(page)s::text IS NULL OR f.page_id = %(page)s)"

# from_home: posted from the owner's home IP (see home_ip.py) — tagged "🏠 you" in the view.
ADMIN_COMMENTS_SQL = f"""
SELECT f.id, f.page_id, f.name, f.body, f.hidden, f.ip_hash, f.created_at,
       f.ip_hash IN (SELECT ip_hash FROM analytics.home_ips) AS from_home,
       v.country, v.device, src.source
FROM analytics.feedback_comments f
{_CONTEXT_JOIN}
WHERE {_PAGE_FILTER}
ORDER BY f.created_at DESC
LIMIT %(limit)s
"""

ADMIN_LIKES_SQL = f"""
SELECT f.page_id, f.ip_hash, f.created_at,
       f.ip_hash IN (SELECT ip_hash FROM analytics.home_ips) AS from_home,
       v.country, v.device, src.source
FROM analytics.feedback_likes f
{_CONTEXT_JOIN}
WHERE {_PAGE_FILTER}
ORDER BY f.created_at DESC
LIMIT %(limit)s
"""

# One row per page that has any feedback — the "by model" table.
ADMIN_BY_PAGE_SQL = """
WITH home AS (SELECT ip_hash FROM analytics.home_ips),
c AS (SELECT page_id, count(*) AS comments,
             count(*) FILTER (WHERE ip_hash IN (SELECT ip_hash FROM home)) AS home_comments,
             max(created_at) AS last_at
      FROM analytics.feedback_comments GROUP BY page_id),
l AS (SELECT page_id, count(*) AS likes,
             count(*) FILTER (WHERE ip_hash IN (SELECT ip_hash FROM home)) AS home_likes,
             max(created_at) AS last_at
      FROM analytics.feedback_likes GROUP BY page_id)
SELECT coalesce(c.page_id, l.page_id)            AS page_id,
       coalesce(c.comments, 0)                   AS comments,
       coalesce(c.home_comments, 0)              AS home_comments,
       coalesce(l.likes, 0)                      AS likes,
       coalesce(l.home_likes, 0)                 AS home_likes,
       greatest(c.last_at, l.last_at)            AS last_at
FROM c FULL OUTER JOIN l ON l.page_id = c.page_id
ORDER BY last_at DESC
"""

ADMIN_COMMENT_SUMMARY_SQL = """
SELECT
    count(*)                              AS total_comments,
    count(*) FILTER (WHERE hidden)        AS hidden_comments,
    count(*) FILTER (WHERE NOT hidden)    AS visible_comments,
    count(DISTINCT page_id)               AS pages_with_comments,
    count(*) FILTER (WHERE ip_hash IN (SELECT ip_hash FROM analytics.home_ips)) AS home_comments,
    (SELECT count(*) FROM analytics.feedback_likes) AS total_likes,
    (SELECT count(*) FROM analytics.feedback_likes
      WHERE ip_hash IN (SELECT ip_hash FROM analytics.home_ips)) AS home_likes
FROM analytics.feedback_comments
"""

TOGGLE_HIDDEN_SQL = """
UPDATE analytics.feedback_comments
SET hidden = NOT hidden
WHERE id = %s
RETURNING id, hidden
"""


def fetch_recent_comments(limit: int = 50, page: Optional[str] = None):
    """Most recent comments (optionally for one page), with country / device / source."""
    with get_cursor() as cur:
        cur.execute(ADMIN_COMMENTS_SQL, {"limit": limit, "page": page})
        return [dict(r) for r in cur.fetchall()]


def fetch_recent_likes(limit: int = 50, page: Optional[str] = None):
    """Most recent likes (optionally for one page), with country / device / source."""
    with get_cursor() as cur:
        cur.execute(ADMIN_LIKES_SQL, {"limit": limit, "page": page})
        return [dict(r) for r in cur.fetchall()]


def fetch_feedback_by_page():
    """Comment and like counts per page, newest activity first."""
    with get_cursor() as cur:
        cur.execute(ADMIN_BY_PAGE_SQL)
        return [dict(r) for r in cur.fetchall()]


def fetch_feedback_summary():
    """Counts for the moderation page header."""
    with get_cursor() as cur:
        cur.execute(ADMIN_COMMENT_SUMMARY_SQL)
        row = cur.fetchone()
        return dict(row) if row else {}


def toggle_comment_hidden(comment_id: int):
    """Flip the hidden boolean. Returns the new state, or None if id not found."""
    with get_cursor() as cur:
        cur.execute(TOGGLE_HIDDEN_SQL, (comment_id,))
        row = cur.fetchone()
        cur.connection.commit()
        return dict(row) if row else None
