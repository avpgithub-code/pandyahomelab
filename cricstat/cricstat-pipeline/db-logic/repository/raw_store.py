"""SQLite raw store: connection, versioned migrations, match upserts, run records.

Transactions are explicit (isolation_level=None + BEGIN/COMMIT/ROLLBACK) so a whole
ingest run is one transaction. journal_mode=DELETE, not WAL: downstream readers will
mount the database read-only, and WAL needs a writable -shm file next to it.
"""
import os
import re
import sqlite3
from typing import Dict, Iterable, List, Optional, Tuple

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "migrations")
_MIGRATION_RE = re.compile(r"^(\d{4})_[\w-]+\.sql$")


def connect(path: str, timeout: float = 30.0) -> sqlite3.Connection:
    """Open (creating parent dirs) with autocommit off-by-hand and DELETE journaling."""
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=timeout, isolation_level=None)
    mode = conn.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
    if mode.lower() != "delete":
        raise sqlite3.OperationalError("could not set journal_mode=DELETE (got %s)" % mode)
    conn.execute("PRAGMA synchronous=FULL")
    return conn


def list_migrations(directory: str = MIGRATIONS_DIR) -> List[Tuple[int, str]]:
    found = []
    for name in sorted(os.listdir(directory)):
        m = _MIGRATION_RE.match(name)
        if m:
            found.append((int(m.group(1)), os.path.join(directory, name)))
    return found


def schema_version(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version ("
                 "version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)")
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return row[0] or 0


def migrate(conn: sqlite3.Connection, now: str, directory: str = MIGRATIONS_DIR) -> List[int]:
    """Apply pending migrations, each in its own transaction. Returns versions applied."""
    current = schema_version(conn)
    applied = []
    for version, path in list_migrations(directory):
        if version <= current:
            continue
        with open(path, encoding="utf-8") as f:
            sql = f.read()
        try:
            # executescript runs statements one by one; the BEGIN/COMMIT make it atomic.
            conn.executescript(
                "BEGIN;\n%s\nINSERT INTO schema_version (version, name, applied_at) "
                "VALUES (%d, '%s', '%s');\nCOMMIT;"
                % (sql, version, os.path.basename(path), now))
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        applied.append(version)
    return applied


class RawStore:
    """Repository over matches_raw and ingest_runs. The caller owns the transaction."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # -- transactions ---------------------------------------------------------------
    def begin(self):
        # IMMEDIATE takes the write lock now, so a second concurrent run fails fast.
        self.conn.execute("BEGIN IMMEDIATE")

    def commit(self):
        self.conn.execute("COMMIT")

    def rollback(self):
        if self.conn.in_transaction:
            self.conn.execute("ROLLBACK")

    # -- reads ----------------------------------------------------------------------
    def snapshot(self) -> Dict[str, Tuple[str, Optional[str]]]:
        """{match_id: (sha256, removed_at)} for every stored match."""
        return {r[0]: (r[1], r[2]) for r in
                self.conn.execute("SELECT match_id, sha256, removed_at FROM matches_raw")}

    def count_active(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM matches_raw WHERE removed_at IS NULL").fetchone()[0]

    def get_match(self, match_id: str) -> Optional[dict]:
        cur = self.conn.execute("SELECT * FROM matches_raw WHERE match_id = ?", (match_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return dict(zip([d[0] for d in cur.description], row))

    def iter_active(self, match_ids: Optional[Iterable[str]] = None):
        """Yield (match_id, sha256, revision, json_zlib) for active matches, oldest first
        (so surrogate keys follow match order). match_ids limits it to those ids."""
        sql = ("SELECT match_id, sha256, revision, json_zlib FROM matches_raw"
               " WHERE removed_at IS NULL")
        if match_ids is None:
            yield from self.conn.execute(sql + " ORDER BY start_date, match_id")
            return
        ids = sorted(match_ids)
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            yield from self.conn.execute(
                sql + " AND match_id IN (%s) ORDER BY start_date, match_id"
                % ", ".join("?" * len(chunk)), chunk)

    def active_hashes(self) -> Dict[str, str]:
        return dict(self.conn.execute(
            "SELECT match_id, sha256 FROM matches_raw WHERE removed_at IS NULL"))

    def latest_run(self, modes: Tuple[str, ...] = ("full", "recent")) -> Optional[dict]:
        cur = self.conn.execute(
            "SELECT * FROM ingest_runs WHERE status = 'success' AND mode IN (%s)"
            " ORDER BY run_id DESC LIMIT 1" % ", ".join("?" * len(modes)), modes)
        row = cur.fetchone()
        return dict(zip([d[0] for d in cur.description], row)) if row else None

    # -- register ---------------------------------------------------------------------
    def register_people(self) -> List[tuple]:
        """[(identifier, name, unique_name, keys_json)]; empty until `register` has run."""
        return self.conn.execute(
            "SELECT identifier, name, unique_name, keys_json FROM register_people").fetchall()

    def register_names(self) -> List[tuple]:
        return self.conn.execute("SELECT identifier, name FROM register_names").fetchall()

    def replace_register(self, people: List[tuple], names: List[tuple]) -> Dict[str, int]:
        """Full replace inside the caller's transaction. Returns added/updated/unchanged/removed
        counts for people (by identifier, comparing every column)."""
        old = {r[0]: r for r in self.register_people()}
        new = {r[0]: r for r in people}
        counts = {"added": sum(1 for k in new if k not in old),
                  "updated": sum(1 for k, r in new.items() if k in old and old[k] != r),
                  "unchanged": sum(1 for k, r in new.items() if old.get(k) == r),
                  "removed": sum(1 for k in old if k not in new)}
        self.conn.execute("DELETE FROM register_people")
        self.conn.execute("DELETE FROM register_names")
        self.conn.executemany("INSERT INTO register_people VALUES (?,?,?,?)", people)
        self.conn.executemany("INSERT OR IGNORE INTO register_names VALUES (?,?)", names)
        return counts

    # -- Wikidata / Commons enrichment (P0.5) -----------------------------------------
    def wikidata_people(self) -> Dict[str, dict]:
        cur = self.conn.execute("SELECT * FROM wikidata_people")
        cols = [d[0] for d in cur.description]
        return {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}

    def upsert_wikidata(self, rows: List[dict], now: str):
        self.conn.executemany(
            "INSERT INTO wikidata_people (cricinfo_id, qid, label_en, date_of_birth, birthplace,"
            " country_for_sport, image_file, fetched_at) VALUES (?,?,?,?,?,?,?,?)"
            " ON CONFLICT(cricinfo_id) DO UPDATE SET qid=excluded.qid, label_en=excluded.label_en,"
            " date_of_birth=excluded.date_of_birth, birthplace=excluded.birthplace,"
            " country_for_sport=excluded.country_for_sport, image_file=excluded.image_file,"
            " fetched_at=excluded.fetched_at",
            [(r["cricinfo_id"], r.get("qid"), r.get("label_en"), r.get("date_of_birth"),
              r.get("birthplace"), r.get("country_for_sport"), r.get("image_file"), now)
             for r in rows])

    def commons_images(self) -> Dict[str, dict]:
        cur = self.conn.execute("SELECT * FROM commons_images")
        cols = [d[0] for d in cur.description]
        return {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}

    def upsert_image(self, name: str, rec: dict, now: str):
        self.conn.execute(
            "INSERT INTO commons_images (image_file, status, licence, licence_url, author,"
            " description_url, thumb_path, width, height, note, fetched_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(image_file) DO UPDATE SET"
            " status=excluded.status, licence=excluded.licence, licence_url=excluded.licence_url,"
            " author=excluded.author, description_url=excluded.description_url,"
            " thumb_path=excluded.thumb_path, width=excluded.width, height=excluded.height,"
            " note=excluded.note, fetched_at=excluded.fetched_at",
            (name, rec["status"], rec.get("licence"), rec.get("licence_url"), rec.get("author"),
             rec.get("description_url"), rec.get("thumb_path"), rec.get("width"),
             rec.get("height"), rec.get("note"), now))

    # -- writes ---------------------------------------------------------------------
    def insert_match(self, rec: dict, now: str, run_id: int):
        self.conn.execute(
            "INSERT INTO matches_raw (match_id, sha256, json_zlib, json_bytes, data_version,"
            " revision, match_type, gender, team_type, start_date, teams, event_name,"
            " first_seen_at, last_seen_at, updated_at, removed_at, last_run_id)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,?)",
            (rec["match_id"], rec["sha256"], rec["json_zlib"], rec["json_bytes"],
             rec["data_version"], rec["revision"], rec["match_type"], rec["gender"],
             rec["team_type"], rec["start_date"], rec["teams"], rec["event_name"],
             now, now, now, run_id))

    def update_match(self, rec: dict, now: str, run_id: int):
        self.conn.execute(
            "UPDATE matches_raw SET sha256=?, json_zlib=?, json_bytes=?, data_version=?,"
            " revision=?, match_type=?, gender=?, team_type=?, start_date=?, teams=?,"
            " event_name=?, last_seen_at=?, updated_at=?, removed_at=NULL, last_run_id=?"
            " WHERE match_id=?",
            (rec["sha256"], rec["json_zlib"], rec["json_bytes"], rec["data_version"],
             rec["revision"], rec["match_type"], rec["gender"], rec["team_type"],
             rec["start_date"], rec["teams"], rec["event_name"], now, now, run_id,
             rec["match_id"]))

    def touch_seen(self, match_ids: Iterable[str], now: str, run_id: int):
        """Unchanged content: bump last_seen_at and clear removed_at."""
        self.conn.executemany(
            "UPDATE matches_raw SET last_seen_at=?, removed_at=NULL, last_run_id=?"
            " WHERE match_id=?", ((now, run_id, m) for m in match_ids))

    def mark_removed(self, match_ids: Iterable[str], now: str):
        self.conn.executemany(
            "UPDATE matches_raw SET removed_at=? WHERE match_id=? AND removed_at IS NULL",
            ((now, m) for m in match_ids))

    # -- run log --------------------------------------------------------------------
    def start_run(self, mode: str, source: str, started_at: str) -> int:
        """Record a 'running' row in its own small transaction, so a crash leaves a trace."""
        self.begin()
        cur = self.conn.execute(
            "INSERT INTO ingest_runs (mode, source, started_at, status) VALUES (?,?,?,?)",
            (mode, source, started_at, "running"))
        self.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int, fields: dict):
        """Update the run row. Called inside the main transaction (success) or alone (fail)."""
        cols = sorted(fields)
        self.conn.execute(
            "UPDATE ingest_runs SET %s WHERE run_id=?" % ", ".join("%s=?" % c for c in cols),
            [fields[c] for c in cols] + [run_id])

    def get_run(self, run_id: int) -> Optional[dict]:
        cur = self.conn.execute("SELECT * FROM ingest_runs WHERE run_id=?", (run_id,))
        row = cur.fetchone()
        return dict(zip([d[0] for d in cur.description], row)) if row else None
