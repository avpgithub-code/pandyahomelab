"""Refresh the Cricsheet Register in the raw store (weekly, F6 §4).

Downloads people.csv and names.csv (or reads local copies), then replaces register_people and
register_names in ONE transaction, logged in ingest_runs with mode='register'. A gate stops a
truncated download from wiping the table: people may not drop by more than 2%.
The next serving-DB build applies the Register to players, player_external_ids and player_names.
"""
import json
import time
from typing import Optional

from db_logic.loaders import downloader, register_csv
from db_logic.repository.raw_store import RawStore, connect, migrate
from shared.exceptions import DataQualityError
from shared.logger import get_logger

log = get_logger("register")


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run(cfg, people_csv: Optional[str] = None, names_csv: Optional[str] = None) -> dict:
    t0 = time.time()
    fetched = []
    if people_csv is None:
        people_csv = _fetch(cfg, cfg.PEOPLE_URL, register_csv.looks_like_people)
        fetched.append(cfg.PEOPLE_URL)
    if names_csv is None:
        names_csv = _fetch(cfg, cfg.NAMES_URL, register_csv.looks_like_names)
        fetched.append(cfg.NAMES_URL)
    people = register_csv.read_people(people_csv)
    names = register_csv.read_names(names_csv)

    started = utcnow()
    conn = connect(cfg.RAW_DB)
    try:
        migrate(conn, started)
        store = RawStore(conn)
        source = "%s + %s" % (people_csv, names_csv)
        run_id = store.start_run("register", source, started)
        summary = {"mode": "register", "run_id": run_id, "people": len(people),
                   "names": len(names), "people_csv": people_csv, "names_csv": names_csv,
                   "started_at": started}
        store.begin()
        try:
            before = len(store.register_people())
            counts = store.replace_register(people, names)
            failures = []
            if not people:
                failures.append("people.csv has no rows")
            elif before and len(people) < before * (1 - cfg.MAX_REGISTER_DROP_FRAC):
                failures.append("register people would drop from %d to %d (more than %.1f%%)"
                                % (before, len(people), 100 * cfg.MAX_REGISTER_DROP_FRAC))
            summary.update(counts, active_before=before, active_after=len(people))
            if failures:
                raise DataQualityError("; ".join(failures), failures)
            store.finish_run(run_id, dict(
                counts, status="success", finished_at=utcnow(), active_before=before,
                active_after=len(people), notes=json.dumps({"names": len(names)})))
            store.commit()
        except BaseException as exc:
            store.rollback()
            status = "dq_failed" if isinstance(exc, DataQualityError) else "error"
            store.begin()
            store.finish_run(run_id, {"status": status, "finished_at": utcnow(),
                                      "notes": json.dumps({"error": str(exc)})})
            store.commit()
            summary.update(status=status, error=str(exc), duration_s=round(time.time() - t0, 1))
            exc.summary = summary
            raise
    finally:
        conn.close()
    for url in fetched:
        for path in downloader.prune(cfg.RAW_ZIP_DIR, url, cfg.KEEP_REGISTER_CSVS):
            log.info("pruned old download %s", path)
    summary.update(status="success", duration_s=round(time.time() - t0, 1))
    log.info("register run %d: %d people (%d added, %d updated, %d removed), %d name variants",
             run_id, len(people), summary["added"], summary["updated"], summary["removed"],
             len(names))
    return summary


def _fetch(cfg, url: str, validate) -> str:
    return downloader.download(url, cfg.RAW_ZIP_DIR, cfg.USER_AGENT, timeout=cfg.HTTP_TIMEOUT,
                               retries=cfg.HTTP_RETRIES, backoff=cfg.HTTP_BACKOFF,
                               validate=validate)
