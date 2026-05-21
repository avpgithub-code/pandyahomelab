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

ADMIN_COMMENTS_SQL = """
SELECT id, page_id, name, body, hidden, ip_hash, created_at
FROM analytics.feedback_comments
ORDER BY created_at DESC
LIMIT %s
"""

ADMIN_COMMENT_SUMMARY_SQL = """
SELECT
    count(*)                              AS total_comments,
    count(*) FILTER (WHERE hidden)        AS hidden_comments,
    count(*) FILTER (WHERE NOT hidden)    AS visible_comments,
    count(DISTINCT page_id)               AS pages_with_comments,
    (SELECT count(*) FROM analytics.feedback_likes) AS total_likes
FROM analytics.feedback_comments
"""

TOGGLE_HIDDEN_SQL = """
UPDATE analytics.feedback_comments
SET hidden = NOT hidden
WHERE id = %s
RETURNING id, hidden
"""


def fetch_recent_comments(limit: int = 50):
    """Return the most recent comments for the moderation view."""
    with get_cursor() as cur:
        cur.execute(ADMIN_COMMENTS_SQL, (limit,))
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
