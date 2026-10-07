"""Build the serving DB (data/db/cricstat.sqlite) from the raw store (F3 §8).

Both modes write `<serving>.new`, run the quality checks, record the build in build_info and only
then os.replace() it over the live file. Readers keep the old file until they reopen. A failed
check leaves the live DB untouched; the rejected file is kept as `<serving>.failed` for inspection.

full         every active raw match → core tables → marts → views → catalog. Bulk-load settings
             (no journal, indexes created after the load).
incremental  copy the live DB, delete + re-insert only the matches whose raw sha256 changed (or
             that were removed), then recompute marts, players, venues, views and catalog. It
             turns into a full build when there is no live DB or when the rules or transform code
             changed (rules_sha), because stored atoms would otherwise follow old rules.
"""
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import time
import zlib
from datetime import datetime, timezone
from typing import Dict, List, Optional

from application_logic.quality import build_checks
from db_logic.repository import bio_store, serving_store
from db_logic.repository.raw_store import RawStore
from db_logic.transforms import match_facts
from shared.exceptions import DataQualityError, PipelineError
from shared.logger import get_logger

log = get_logger("build")
MODES = ("full", "incremental")
SCHEMA_VERSION = 1
_COMMIT_EVERY = 1000
_HERE = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(os.path.dirname(_HERE))
# Anything that changes what the stored rows mean → a full rebuild.
_RULE_FILES = ("serving_schema.sql", "reference_data.sql")
_CODE_FILES = (os.path.join(_PIPELINE, "db-logic", "transforms", "match_facts.py"),
               os.path.join(_PIPELINE, "db-logic", "repository", "serving_store.py"))
# Cheap inputs an incremental build re-applies; a no-op build is skipped only if none changed.
_INPUT_FILES = ("semantic_views.sql", "semantic_catalog.sql")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(paths: List[str], extra: str = "") -> str:
    h = hashlib.sha256(extra.encode())
    for p in paths:
        with open(p, "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:16]


def read_venue_map(path: Optional[str]) -> List[dict]:
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        # Not stripped: names must match Cricsheet byte for byte (one starts with a space).
        return [{k: v or "" for k, v in row.items()} for row in csv.DictReader(f)]


def _previous(serving_db: str) -> Optional[dict]:
    """Last successful build of the live DB: build_id, notes, all build_info rows."""
    if not os.path.exists(serving_db):
        return None
    conn = sqlite3.connect("file:%s?mode=ro" % serving_db, uri=True)
    try:
        cur = conn.execute("SELECT * FROM build_info ORDER BY build_id")
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    except sqlite3.DatabaseError as exc:
        log.warning("cannot read build_info from %s (%s); doing a full build", serving_db, exc)
        return None
    finally:
        conn.close()
    ok = [r for r in rows if r["status"] == "success"]
    if not ok:
        return None
    notes = json.loads(ok[-1]["notes"] or "{}")
    return {"build_id": rows[-1]["build_id"], "notes": notes, "rows": rows}


def _open_new(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None)
    _bulk_pragmas(conn)
    return conn


def _bulk_pragmas(conn: sqlite3.Connection) -> None:
    # The .new file is scratch until the swap: if the process dies, it is simply rebuilt.
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA cache_size = -262144")       # 256 MB
    conn.execute("PRAGMA temp_store = MEMORY")        # never spill to the NAS's small /var/tmp


class _Job:
    """State of one build run, shared by the steps below."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def build(raw_db: str, serving_db: str, sql_dir: str, mode: str = "incremental",
          venue_map_path: Optional[str] = None, photo_dir: Optional[str] = None,
          blocklist_path: Optional[str] = None) -> Dict[str, object]:
    """Build and swap. Returns the summary; raises DataQualityError (exit 2) or PipelineError."""
    if mode not in MODES:
        raise ValueError("mode must be one of %s" % (MODES,))
    if not os.path.exists(raw_db):
        raise PipelineError("raw store not found: %s" % raw_db)
    rules_sha = _sha([os.path.join(sql_dir, n) for n in _RULE_FILES] + list(_CODE_FILES),
                     "schema-%d" % SCHEMA_VERSION)
    venue_rows = read_venue_map(venue_map_path)
    prev = _previous(serving_db)
    used, escalated = mode, None
    if mode == "incremental":
        if prev is None:
            used, escalated = "full", "no live serving DB"
        elif prev["notes"].get("rules_sha") != rules_sha:
            used, escalated = "full", "rules or transform code changed"
    job = _Job(t0=time.time(), sql_dir=sql_dir, serving_db=serving_db, tmp=serving_db + ".new",
               used=used, prev=prev, venue_rows=venue_rows, rules_sha=rules_sha,
               photo_dir=photo_dir, blocklist=bio_store.read_blocklist(blocklist_path),
               summary={"mode": "build-" + used, "requested": mode, "escalated": escalated,
                        "started_at": utcnow(), "status": "running", "rules_sha": rules_sha},
               tally={"unresolved": set(), "problems": [], "raw_deliveries": 0})

    raw = sqlite3.connect("file:%s?mode=ro" % raw_db, uri=True)
    try:
        job.store = RawStore(raw)
        job.raw_hashes = job.store.active_hashes()
        job.people = [(i, n, u, json.loads(k)) for i, n, u, k in job.store.register_people()]
        job.names = job.store.register_names()
        job.last_run = job.store.latest_run() or {}
        job.reg_run = job.store.latest_run(("register",)) or {}
        job.wiki, job.images = bio_store.read_enrichment(raw)
        enrich_run = (job.store.latest_run(("enrich",)) or {}) if job.wiki else {}
        job.inputs_sha = _sha([os.path.join(sql_dir, n) for n in _INPUT_FILES]
                              + [serving_store.MARTS_SQL, os.path.abspath(__file__),
                                 bio_store.__file__]
                              + ([venue_map_path] if venue_rows else [])
                              + ([blocklist_path] if blocklist_path
                                 and os.path.exists(blocklist_path) else []),
                              "register-%s enrich-%s" % (job.reg_run.get("run_id"),
                                                         enrich_run.get("run_id")))
        if os.path.exists(job.tmp):
            os.remove(job.tmp)
        os.makedirs(os.path.dirname(os.path.abspath(serving_db)), exist_ok=True)
        if used == "incremental" and not _plan_incremental(job):
            return job.summary                      # nothing changed: live DB kept
        try:
            _fill(job)
        except BaseException:
            if os.path.exists(job.tmp):
                os.remove(job.tmp)                  # never leave a half-built file behind
            raise
        return _check_and_swap(job)
    finally:
        raw.close()


def _plan_incremental(job: _Job) -> bool:
    """Work out which matches changed. False when nothing at all changed."""
    serving_ids = _serving_hashes(job.serving_db)
    job.changed = sorted(m for m, h in job.raw_hashes.items()
                         if serving_ids.get(m, (None, None))[1] != h)
    job.removed = sorted(m for m in serving_ids if m not in job.raw_hashes)
    job.stale = [serving_ids[m][0] for m in job.changed + job.removed if m in serving_ids]
    job.summary.update(changed_matches=len(job.changed), removed_matches=len(job.removed))
    if (not job.changed and not job.removed
            and job.prev["notes"].get("inputs_sha") == job.inputs_sha):
        job.summary.update(status="unchanged", build_id=job.prev["build_id"],
                           duration_s=round(time.time() - job.t0, 1))
        log.info("nothing changed since build %s; live DB kept", job.prev["build_id"])
        return False
    return True


def _fill(job: _Job) -> None:
    """Write everything into the .new file and measure it."""
    s = job.summary
    if job.used == "full":
        job.changed, job.removed = list(job.raw_hashes), []
        conn = _open_new(job.tmp)
        deferred = serving_store.create_schema(conn, job.sql_dir, defer_indexes=True)
        _bulk_pragmas(conn)          # the schema script turned journaling and FKs back on
        if job.prev is not None:
            _copy_history(conn, job.prev["rows"])
    else:
        t = time.time()
        shutil.copyfile(job.serving_db, job.tmp)
        s["copy_s"] = round(time.time() - t, 1)
        conn = _open_new(job.tmp)
        deferred = []
        conn.execute("BEGIN")
        serving_store.delete_matches(conn, job.stale)
        conn.execute("COMMIT")
    try:
        job.build_id = (job.prev["build_id"] + 1) if job.prev else 1
        t = time.time()
        _load_matches(conn, job.store, None if job.used == "full" else job.changed, job.tally)
        s["load_s"] = round(time.time() - t, 1)

        t = time.time()
        conn.execute("BEGIN")
        serving_store.load_players(conn, job.people, job.names)
        bio, s["bio"] = bio_store.bio_rows(job.people, job.wiki, job.images, job.photo_dir,
                                           job.blocklist, datetime.now(timezone.utc).date())
        bio_store.apply_bio(conn, bio)
        venues = serving_store.apply_venue_map(conn, job.venue_rows)
        conn.execute("COMMIT")
        for stmt in deferred:
            conn.execute(stmt)
        # executescript() commits as it goes; fine on the scratch .new file.
        serving_store.build_marts(conn)
        serving_store.create_views(conn, job.sql_dir)
        s["catalog_rows"] = serving_store.load_catalog(conn, job.sql_dir)
        conn.execute("ANALYZE" if job.used == "full" else "PRAGMA optimize")
        s["post_s"] = round(time.time() - t, 1)

        t = time.time()
        m = serving_store.measure(conn)
        m.update(raw_active=len(job.raw_hashes), unresolved_names=len(job.tally["unresolved"]),
                 transform_problems=len(job.tally["problems"]),
                 raw_deliveries=job.tally["raw_deliveries"] if job.used == "full" else None,
                 venues_unmapped=venues["venues_unmapped"])
        job.failures, job.warnings = build_checks.evaluate(m)
        s["check_s"] = round(time.time() - t, 1)
        data_as_of = conn.execute("SELECT MAX(end_date) FROM matches").fetchone()[0]
        notes = {"rules_sha": job.rules_sha, "inputs_sha": job.inputs_sha,
                 "warnings": job.warnings, "failures": job.failures,
                 "changed": len(job.changed), "removed": len(job.removed),
                 "raw_last_run_finished": job.last_run.get("finished_at"),
                 "register_run_id": job.reg_run.get("run_id"), "escalated": s["escalated"]}
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO build_info (build_id, built_at, mode, raw_run_id, matches, deliveries,"
            " data_as_of, status, notes) VALUES (?,?,?,?,?,?,?,?,?)",
            (job.build_id, utcnow(), job.used, job.last_run.get("run_id"), m["matches"],
             m["deliveries"], data_as_of, "dq_failed" if job.failures else "success",
             json.dumps(notes, sort_keys=True)))
        conn.execute("INSERT OR REPLACE INTO schema_version VALUES (?,?,?)",
                     (SCHEMA_VERSION, utcnow(), "F3 serving schema"))
        conn.execute("COMMIT")
        s.update(build_id=job.build_id, data_as_of=data_as_of, checks=m, warnings=job.warnings,
                 venues=venues, unresolved_sample=sorted(job.tally["unresolved"])[:20],
                 problems_sample=job.tally["problems"][:20],
                 row_counts=serving_store.row_counts(conn))
        conn.execute("PRAGMA journal_mode = DELETE")   # readers mount read-only (F3 §1)
        conn.execute("PRAGMA synchronous = FULL")
    finally:
        conn.close()


def _check_and_swap(job: _Job) -> Dict[str, object]:
    s = job.summary
    s["db_bytes"] = os.path.getsize(job.tmp)
    if job.failures:
        os.replace(job.tmp, job.serving_db + ".failed")
        s.update(status="dq_failed", failures=job.failures,
                 duration_s=round(time.time() - job.t0, 1))
        log.error("build %d failed its checks; live DB kept: %s", job.build_id,
                  "; ".join(job.failures))
        exc = DataQualityError("; ".join(job.failures), job.failures)
        exc.summary = s
        raise exc
    _fsync(job.tmp)
    os.replace(job.tmp, job.serving_db)
    s.update(status="success", finished_at=utcnow(), duration_s=round(time.time() - job.t0, 1))
    log.info("build %d (%s) swapped in: %d matches, %d deliveries, %.0f MB in %.0fs",
             job.build_id, job.used, s["checks"]["matches"], s["checks"]["deliveries"],
             s["db_bytes"] / 1e6, s["duration_s"])
    for w in job.warnings:
        log.warning(w)
    return s


def _serving_hashes(serving_db: str) -> Dict[str, tuple]:
    conn = sqlite3.connect("file:%s?mode=ro" % serving_db, uri=True)
    try:
        return {mid: (key, sha) for key, mid, sha in conn.execute(
            "SELECT match_key, match_id, source_sha256 FROM matches")}
    finally:
        conn.close()


def _copy_history(conn: sqlite3.Connection, rows: List[dict]) -> None:
    conn.executemany(
        "INSERT INTO build_info (build_id, built_at, mode, raw_run_id, matches, deliveries,"
        " data_as_of, status, notes) VALUES (:build_id, :built_at, :mode, :raw_run_id, :matches,"
        " :deliveries, :data_as_of, :status, :notes)", rows)


def _load_matches(conn: sqlite3.Connection, store: RawStore, match_ids, tally: dict) -> None:
    rules = serving_store.load_rules(conn)
    keys = serving_store.Keys(conn)
    n = 0
    conn.execute("BEGIN")
    for match_id, sha, revision, blob in store.iter_active(match_ids):
        doc = json.loads(zlib.decompress(blob))
        facts = match_facts.build_facts(match_id, doc, rules)
        tally["raw_deliveries"] += facts.n_deliveries
        tally["unresolved"].update("%s: %s" % (match_id, u) for u in facts.unresolved)
        tally["problems"] += ["%s: %s" % (match_id, p) for p in facts.problems]
        if facts.match["format_key"] is None:
            continue                                   # counted as a problem; fails the build
        serving_store.insert_match(conn, keys, facts, sha, revision)
        n += 1
        if n % _COMMIT_EVERY == 0:
            conn.execute("COMMIT")
            log.info("loaded %d matches", n)
            conn.execute("BEGIN")
    conn.execute("COMMIT")
    log.info("loaded %d matches", n)


def _fsync(path: str) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def run(cfg, mode: str) -> Dict[str, object]:
    """CLI entry: paths from config."""
    return build(cfg.RAW_DB, cfg.SERVING_DB, cfg.SQL_DIR, mode=mode,
                 venue_map_path=cfg.VENUE_MAP, photo_dir=cfg.PHOTO_DIR,
                 blocklist_path=cfg.PHOTO_BLOCKLIST)
