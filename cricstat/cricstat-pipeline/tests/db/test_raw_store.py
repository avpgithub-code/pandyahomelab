"""Tests for db-logic/repository — migrations, journal mode, schema."""
import sqlite3

from db_logic.repository.raw_store import RawStore, connect, list_migrations, migrate


def test_migrations_are_versioned_and_idempotent(db_path):
    conn = connect(db_path)
    assert migrate(conn, "2026-10-05T00:00:00Z") == [1, 2, 3]
    assert migrate(conn, "2026-10-05T00:00:01Z") == []
    rows = conn.execute("SELECT version, name FROM schema_version").fetchall()
    assert rows == [(1, "0001_init.sql"), (2, "0002_register.sql"), (3, "0003_wikidata.sql")]
    assert [v for v, _ in list_migrations()] == [1, 2, 3]


def test_journal_mode_is_delete_not_wal(db_path):
    conn = connect(db_path)
    migrate(conn, "t")
    conn.close()
    raw = sqlite3.connect(db_path)
    assert raw.execute("PRAGMA journal_mode").fetchone()[0] == "delete"


def test_tables_and_indexes(db_path):
    conn = connect(db_path)
    migrate(conn, "t")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(matches_raw)")}
    assert {"match_id", "sha256", "json_zlib", "match_type", "gender", "team_type",
            "start_date", "teams", "event_name", "first_seen_at", "last_seen_at",
            "updated_at", "removed_at"} <= cols
    run_cols = {r[1] for r in conn.execute("PRAGMA table_info(ingest_runs)")}
    assert {"run_id", "mode", "source", "started_at", "finished_at", "status", "added",
            "updated", "unchanged", "failed", "removed", "notes"} <= run_cols
    idx = {r[1] for r in conn.execute("PRAGMA index_list(matches_raw)")}
    assert {"ix_matches_raw_start_date", "ix_matches_raw_match_type",
            "ix_matches_raw_gender"} <= idx


def test_failed_migration_rolls_back(tmp_path, db_path):
    (tmp_path / "m").mkdir()
    (tmp_path / "m" / "0001_ok.sql").write_text("CREATE TABLE a (x);")
    (tmp_path / "m" / "0002_bad.sql").write_text("CREATE TABLE b (x); NOT SQL;")
    conn = connect(db_path)
    try:
        migrate(conn, "t", str(tmp_path / "m"))
    except sqlite3.OperationalError:
        pass
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "a" in tables and "b" not in tables
    assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 1


def test_start_run_commits_running_row(db_path):
    conn = connect(db_path)
    migrate(conn, "t")
    store = RawStore(conn)
    run_id = store.start_run("full", "x.zip", "t")
    assert not conn.in_transaction
    assert store.get_run(run_id)["status"] == "running"
