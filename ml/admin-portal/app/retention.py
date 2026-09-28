"""Data retention — enforces what the public /privacy/ page promises.

Daily, in the admin-portal process:
  - page_views, page_events, visitor_events older than 13 months → deleted
  - likes and comments older than 13 months → kept, but the IP hash is replaced
    with the "unknown" placeholder, so they can no longer be tied to a visitor
Raw IPs only exist in the nginx access log, which rotate-logs.sh keeps ~12 weeks.
"""
import asyncio
import logging

from app.db import get_cursor

logger = logging.getLogger("admin-portal.retention")

RUN_EVERY_SECONDS = 24 * 60 * 60
KEEP = "13 months"
UNKNOWN_HASH = "0" * 64

STATEMENTS = [
    ("page_events",    f"DELETE FROM analytics.page_events    WHERE created_at  < NOW() - INTERVAL '{KEEP}'"),
    ("page_views",     f"DELETE FROM analytics.page_views     WHERE started_at  < NOW() - INTERVAL '{KEEP}'"),
    ("visitor_events", f"DELETE FROM analytics.visitor_events WHERE occurred_at < NOW() - INTERVAL '{KEEP}'"),
    ("feedback_likes", f"UPDATE analytics.feedback_likes SET ip_hash = '{UNKNOWN_HASH}' "
                       f"WHERE created_at < NOW() - INTERVAL '{KEEP}' AND ip_hash <> '{UNKNOWN_HASH}'"),
    ("feedback_comments", f"UPDATE analytics.feedback_comments SET ip_hash = '{UNKNOWN_HASH}' "
                          f"WHERE created_at < NOW() - INTERVAL '{KEEP}' AND ip_hash <> '{UNKNOWN_HASH}'"),
]


def apply_retention() -> dict:
    counts = {}
    with get_cursor() as cur:
        for table, sql in STATEMENTS:
            cur.execute(sql)
            counts[table] = cur.rowcount
        cur.connection.commit()
    return counts


async def retention_loop() -> None:
    loop = asyncio.get_running_loop()
    while True:
        try:
            counts = await loop.run_in_executor(None, apply_retention)
            if any(counts.values()):
                logger.info(f"retention applied: {counts}")
        except Exception as e:
            logger.warning(f"retention run failed: {e}")
        await asyncio.sleep(RUN_EVERY_SECONDS)
