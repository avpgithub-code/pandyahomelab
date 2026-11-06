"""All analytics SQL lives here. Parameterised by window-in-days (see app/window.py)."""
from typing import Dict, List

from app.db import get_cursor
from app.window import win_param


SUMMARY_SQL = """
SELECT
    count(*)                                                   AS total_events,
    count(*) FILTER (WHERE NOT is_bot)                         AS real_events,
    count(*) FILTER (WHERE is_bot)                             AS bot_events,
    count(DISTINCT ip_hash) FILTER (WHERE NOT is_bot)          AS unique_visitors,
    count(DISTINCT path)                                       AS unique_paths
FROM analytics.visitor_events
WHERE occurred_at >= date_trunc('day', NOW()) - %s::interval
"""

DAILY_SQL = """
SELECT
    date_trunc('day', occurred_at)::date                       AS day,
    count(*)                                                   AS events,
    count(*) FILTER (WHERE NOT is_bot)                         AS real_events,
    count(DISTINCT ip_hash) FILTER (WHERE NOT is_bot)          AS unique_visitors,
    count(*) FILTER (WHERE is_bot)                             AS bot_events
FROM analytics.visitor_events
WHERE occurred_at >= date_trunc('day', NOW()) - %s::interval
GROUP BY 1
ORDER BY 1 DESC
"""

TOP_PATHS_SQL = """
SELECT
    path,
    count(*)                                                   AS visits
FROM analytics.visitor_events
WHERE NOT is_bot
  AND occurred_at >= date_trunc('day', NOW()) - %s::interval
GROUP BY path
ORDER BY visits DESC
LIMIT %s
"""

COUNTRIES_SQL = """
SELECT
    country,
    count(DISTINCT ip_hash)                                    AS visitors,
    count(*)                                                   AS visits
FROM analytics.visitor_events
WHERE NOT is_bot
  AND country IS NOT NULL
  AND occurred_at >= date_trunc('day', NOW()) - %s::interval
GROUP BY country
ORDER BY visitors DESC
LIMIT %s
"""

# Domain-normalise the referrer in SQL:
#   - strip protocol + optional www.
#   - keep everything up to next /, ?, or #
#   - empty / null / non-matching → '(direct)'
REFERRERS_SQL = """
SELECT
    COALESCE(
        NULLIF(
            substring(referrer FROM '^https?://(?:www\\.)?([^/?#]+)'),
            ''
        ),
        '(direct)'
    )                                                          AS domain,
    count(*)                                                   AS visits
FROM analytics.visitor_events
WHERE NOT is_bot
  AND occurred_at >= date_trunc('day', NOW()) - %s::interval
GROUP BY domain
ORDER BY visits DESC
LIMIT %s
"""


def fetch_summary(days: int) -> Dict:
    with get_cursor() as cur:
        cur.execute(SUMMARY_SQL, (win_param(days),))
        row = cur.fetchone()
        return dict(row) if row else {}


def fetch_daily(days: int) -> List[Dict]:
    with get_cursor() as cur:
        cur.execute(DAILY_SQL, (win_param(days),))
        return [dict(r) for r in cur.fetchall()]


def fetch_top_paths(days: int, limit: int = 5) -> List[Dict]:
    with get_cursor() as cur:
        cur.execute(TOP_PATHS_SQL, (win_param(days), limit))
        return [dict(r) for r in cur.fetchall()]


def fetch_countries(days: int, limit: int = 10) -> List[Dict]:
    with get_cursor() as cur:
        cur.execute(COUNTRIES_SQL, (win_param(days), limit))
        return [dict(r) for r in cur.fetchall()]


def fetch_referrers(days: int, limit: int = 10) -> List[Dict]:
    with get_cursor() as cur:
        cur.execute(REFERRERS_SQL, (win_param(days), limit))
        return [dict(r) for r in cur.fetchall()]
