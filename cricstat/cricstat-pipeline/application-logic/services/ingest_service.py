"""Ingest one Cricsheet zip into the raw store.

The whole run is ONE transaction:
  BEGIN IMMEDIATE -> upsert every match -> (full) mark missing ids removed
  -> data-quality gates -> COMMIT, or ROLLBACK on any failure.
The ingest_runs row is written 'running' first, finalised inside the transaction on
success, and in a separate small transaction after a rollback.

Upsert by match_id with a sha256 of the file bytes:
  new id -> added; hash changed -> updated; same hash -> unchanged (last_seen_at bumped).
A previously removed id that shows up again has removed_at cleared (restored).
Unchanged files are not re-parsed: their bytes match a file that already passed.
"""
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from application_logic.quality import gates
from db_logic.loaders.cricsheet_zip import CricsheetZip, file_sha256
from db_logic.repository.raw_store import RawStore, connect, migrate
from db_logic.transforms.match_record import MatchParseError, build_record, sha256_hex
from shared.exceptions import DataQualityError
from shared.logger import get_logger

log = get_logger("ingest")
MODES = ("full", "recent")
_SAMPLE = 20          # bad ids kept in notes
_TOUCH_BATCH = 2000


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class IngestResult(dict):
    """The run summary (also the stdout JSON line)."""


def ingest_zip(db_path: str, zip_path: str, mode: str, source: Optional[str] = None,
               max_failed_abs: int = 5, max_failed_frac: float = 0.005,
               max_active_drop_frac: float = 0.02,
               source_last_modified: Optional[str] = None) -> IngestResult:
    """Ingest zip_path. Raises DataQualityError (rolled back) or other errors (rolled back).
    source_last_modified: when the source last changed the downloaded file (HTTP Last-Modified),
    kept in the run's notes so "Cricsheet hasn't published" is visible, not inferred."""
    if mode not in MODES:
        raise ValueError("mode must be one of %s" % (MODES,))
    t0 = time.time()
    started = utcnow()
    conn = connect(db_path)
    try:
        migrate(conn, started)
        store = RawStore(conn)
        source = source or zip_path
        run_id = store.start_run(mode, source, started)
        counts = {"added": 0, "updated": 0, "unchanged": 0, "failed": 0,
                  "removed": 0, "restored": 0, "skipped": 0}
        notes: Dict[str, object] = {}
        if source_last_modified:
            notes["source_last_modified"] = source_last_modified
        summary = IngestResult(run_id=run_id, mode=mode, source=source, status="running",
                               started_at=started, source_last_modified=source_last_modified)
        try:
            zf = CricsheetZip(zip_path)
            src_sha = file_sha256(zip_path)
            summary["source_sha256"] = src_sha
            store.begin()
            existing = store.snapshot()
            active_before = sum(1 for _, removed in existing.values() if removed is None)
            seen = set()
            bad_files: List[str] = []
            nondigit: List[str] = []
            duplicates: List[str] = []
            touch: List[str] = []
            now = started
            json_files = 0

            for member in zf:
                json_files += 1
                mid = member.match_id
                if mid in seen:
                    counts["failed"] += 1
                    duplicates.append(member.name)
                    continue
                seen.add(mid)
                if not mid.isdigit():
                    nondigit.append(mid)
                digest = sha256_hex(member.raw)
                prev = existing.get(mid)
                if prev is not None and prev[0] == digest:
                    counts["unchanged"] += 1
                    if prev[1] is not None:
                        counts["restored"] += 1
                    touch.append(mid)
                    if len(touch) >= _TOUCH_BATCH:
                        store.touch_seen(touch, now, run_id)
                        touch = []
                    continue
                try:
                    rec = build_record(mid, member.raw, digest)
                except MatchParseError as exc:
                    counts["failed"] += 1
                    if len(bad_files) < _SAMPLE:
                        bad_files.append("%s: %s" % (member.name, exc))
                    log.warning("skipping %s: %s", member.name, exc)
                    continue
                if prev is None:
                    store.insert_match(rec, now, run_id)
                    counts["added"] += 1
                else:
                    store.update_match(rec, now, run_id)
                    counts["updated"] += 1
                    if prev[1] is not None:
                        counts["restored"] += 1
            if touch:
                store.touch_seen(touch, now, run_id)
            counts["skipped"] = len(zf.skipped)

            if mode == "full":
                # Ids seen but unparseable stay as they are: present, just not refreshed.
                gone = [m for m, (_, removed) in existing.items()
                        if removed is None and m not in seen]
                store.mark_removed(gone, now)
                counts["removed"] = len(gone)
                if gone:
                    notes["removed_ids"] = sorted(gone)[:_SAMPLE]
            active_after = store.count_active()

            if nondigit:
                notes["nondigit_match_ids"] = sorted(nondigit)[:_SAMPLE]
                log.warning("%d match ids are not digits-only (stored anyway): %s",
                            len(nondigit), ", ".join(sorted(nondigit)[:5]))
            if bad_files:
                notes["failed_files"] = bad_files
            if duplicates:
                notes["duplicate_members"] = duplicates[:_SAMPLE]
            if zf.skipped:
                notes["skipped_members"] = zf.skipped[:_SAMPLE]

            summary.update(counts, json_files=json_files, nondigit_ids=len(nondigit),
                           active_before=active_before, active_after=active_after)

            failures = gates.evaluate(mode, json_files, counts["failed"], active_before,
                                      active_after, max_failed_abs, max_failed_frac,
                                      max_active_drop_frac)
            if failures:
                notes["gate_failures"] = failures
                raise DataQualityError("; ".join(failures), failures)

            finished = utcnow()
            summary.update(status="success", finished_at=finished,
                           duration_s=round(time.time() - t0, 1))
            store.finish_run(run_id, dict(
                counts, status="success", finished_at=finished, source_sha256=src_sha,
                active_before=active_before, active_after=active_after,
                notes=json.dumps(notes, sort_keys=True) if notes else None))
            store.commit()
            log.info("run %d %s committed: %s", run_id, mode, _fmt(summary))
            return summary
        except BaseException as exc:
            store.rollback()
            status = "dq_failed" if isinstance(exc, DataQualityError) else "error"
            if status == "error":
                notes["error"] = "%s: %s" % (type(exc).__name__, exc)
            finished = utcnow()
            summary.update(counts, status=status, finished_at=finished,
                           duration_s=round(time.time() - t0, 1), error=str(exc))
            try:
                store.begin()
                store.finish_run(run_id, dict(
                    counts, status=status, finished_at=finished,
                    source_sha256=summary.get("source_sha256"),
                    active_before=summary.get("active_before"),
                    active_after=summary.get("active_after"),
                    notes=json.dumps(notes, sort_keys=True)))
                store.commit()
            except Exception:  # never mask the original failure
                store.rollback()
                log.exception("could not record failed run %d", run_id)
            log.error("run %d %s rolled back (%s): %s", run_id, mode, status, exc)
            exc.summary = summary
            raise
    finally:
        conn.close()


def _fmt(summary) -> str:
    keys = ("added", "updated", "unchanged", "failed", "removed", "restored", "skipped",
            "active_before", "active_after", "duration_s")
    return " ".join("%s=%s" % (k, summary.get(k)) for k in keys)
