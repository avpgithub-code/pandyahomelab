"""Entrypoint: tail Nginx JSON log, enrich, batch-insert into PostgreSQL.

Loop runs forever. Polls every POLL_INTERVAL_SECONDS seconds.
Restarts gracefully via Docker's `restart: unless-stopped` on uncaught errors.
"""
import logging
import os
import sys
import time

from ingester.checkpoint import Checkpoint
from ingester.enricher import enrich
from ingester.parser import parse_line
from ingester.schema import ensure_schema
from ingester.tailer import LogTailer
from ingester.writer import Writer

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ingester")


def main() -> int:
    poll_interval = float(os.environ.get("POLL_INTERVAL_SECONDS", "2"))
    log_path = os.environ.get("LOG_PATH", "/logs/access.json.log")
    checkpoint_path = os.environ.get("CHECKPOINT_PATH", "/checkpoint/state.json")
    database_url = os.environ.get("DATABASE_URL")
    ip_salt = os.environ.get("ANALYTICS_IP_SALT")

    if not database_url:
        logger.error("DATABASE_URL env var required")
        return 1
    if not ip_salt or len(ip_salt) < 16:
        logger.error("ANALYTICS_IP_SALT env var required (min 16 chars; recommended: openssl rand -hex 32)")
        return 1

    logger.info(f"starting analytics-ingester  log={log_path}  poll={poll_interval}s")

    # Bootstrap PostgreSQL schema (idempotent)
    ensure_schema(database_url)

    checkpoint = Checkpoint(checkpoint_path)
    saved_offset, saved_inode = checkpoint.read()
    logger.info(f"resuming from offset={saved_offset} inode={saved_inode}")

    tailer = LogTailer(log_path, start_offset=saved_offset, start_inode=saved_inode)
    writer = Writer(database_url)

    inserted_total = 0
    skipped_total = 0

    while True:
        try:
            new_lines = tailer.read_new()
            if not new_lines:
                time.sleep(poll_interval)
                continue

            rows = []
            for line in new_lines:
                try:
                    event = parse_line(line)
                    event = enrich(event, ip_salt)
                    rows.append(event)
                except Exception as parse_err:
                    skipped_total += 1
                    logger.warning(f"skipping malformed line: {parse_err!r}  raw={line[:200]!r}")

            if rows:
                writer.insert_batch(rows)
                checkpoint.write(tailer.position, tailer.inode)
                inserted_total += len(rows)
                logger.info(
                    f"inserted batch={len(rows)} total_inserted={inserted_total} "
                    f"total_skipped={skipped_total}"
                )

        except KeyboardInterrupt:
            logger.info("shutdown requested")
            return 0
        except Exception as loop_err:
            # Don't lose the position we already saved. Sleep and retry.
            logger.exception(f"loop error (will retry): {loop_err!r}")
            time.sleep(min(30, poll_interval * 5))


if __name__ == "__main__":
    sys.exit(main())
