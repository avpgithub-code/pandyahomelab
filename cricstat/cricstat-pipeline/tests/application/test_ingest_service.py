"""Tests for application-logic/services/ingest_service — upsert semantics, removal,
idempotency, and rollback when a data-quality gate fails."""
import json
import sqlite3

import pytest

from application_logic.services.ingest_service import ingest_zip
from db_logic.repository.raw_store import RawStore, connect
from db_logic.transforms.match_record import decompress
from shared.exceptions import DataQualityError
from tests.conftest import match_bytes


def _files(ids, **kw):
    return {i: match_bytes(i, **kw) for i in ids}


def _store(db_path):
    return RawStore(connect(db_path))


def test_first_load_adds_everything(db_path, make_zip):
    s = ingest_zip(db_path, make_zip(_files(["1", "2", "3"])), "full")
    assert (s["added"], s["updated"], s["unchanged"], s["failed"]) == (3, 0, 0, 0)
    assert s["skipped"] == 1 and s["status"] == "success"
    row = _store(db_path).get_match("2")
    assert row["match_type"] == "T20" and row["removed_at"] is None
    assert decompress(row["json_zlib"]) == match_bytes("2")


def test_rerun_same_zip_is_idempotent(db_path, make_zip):
    path = make_zip(_files(["1", "2", "3"]))
    ingest_zip(db_path, path, "full")
    before = _store(db_path).get_match("1")
    s = ingest_zip(db_path, path, "full")
    assert (s["added"], s["updated"], s["unchanged"], s["removed"]) == (0, 0, 3, 0)
    after = _store(db_path).get_match("1")
    assert after["updated_at"] == before["updated_at"]
    assert after["first_seen_at"] == before["first_seen_at"]
    assert after["last_run_id"] == s["run_id"]


def test_changed_content_is_updated(db_path, make_zip):
    ingest_zip(db_path, make_zip(_files(["1", "2"])), "full")
    files = _files(["1", "2"])
    files["2"] = match_bytes("2", revision=2, runs=4)
    s = ingest_zip(db_path, make_zip(files), "recent")
    assert (s["added"], s["updated"], s["unchanged"]) == (0, 1, 1)
    assert _store(db_path).get_match("2")["revision"] == 2


def test_full_marks_missing_removed_and_restores(db_path, make_zip):
    many = [str(i) for i in range(1, 101)]
    ingest_zip(db_path, make_zip(_files(many)), "full")
    s = ingest_zip(db_path, make_zip(_files(many[:-2])), "full")   # 2% drop: allowed
    assert s["removed"] == 2 and s["active_after"] == 98
    store = _store(db_path)
    assert store.get_match("100")["removed_at"] is not None  # never deleted
    assert store.conn.execute("SELECT COUNT(*) FROM matches_raw").fetchone()[0] == 100

    s = ingest_zip(db_path, make_zip(_files(many)), "full")
    assert s["restored"] == 2 and s["unchanged"] == 100 and s["removed"] == 0
    assert _store(db_path).get_match("100")["removed_at"] is None


def test_recent_never_removes(db_path, make_zip):
    ingest_zip(db_path, make_zip(_files(["1", "2", "3"])), "full")
    s = ingest_zip(db_path, make_zip(_files(["4"])), "recent")
    assert s["added"] == 1 and s["removed"] == 0 and s["active_after"] == 4


def test_recent_restores_a_removed_match(db_path, make_zip):
    ids = [str(i) for i in range(1, 101)]
    ingest_zip(db_path, make_zip(_files(ids)), "full")
    ingest_zip(db_path, make_zip(_files(ids[1:])), "full")
    s = ingest_zip(db_path, make_zip(_files(["1"])), "recent")
    assert s["restored"] == 1 and _store(db_path).get_match("1")["removed_at"] is None


def _snapshot(db_path):
    conn = sqlite3.connect(db_path)
    return conn.execute("SELECT match_id, sha256, last_seen_at, removed_at FROM matches_raw"
                        " ORDER BY match_id").fetchall()


def test_too_many_parse_failures_rolls_back(db_path, make_zip):
    ingest_zip(db_path, make_zip(_files(["1", "2"])), "full")
    before = _snapshot(db_path)
    files = _files(["1", "2", "3"], revision=9)
    files.update({str(i): b"{broken" for i in range(10, 16)})   # 6 > max(5, 0.5%)
    with pytest.raises(DataQualityError) as err:
        ingest_zip(db_path, make_zip(files), "recent")
    assert err.value.summary["status"] == "dq_failed"
    assert _snapshot(db_path) == before      # nothing from the run survived
    run = _store(db_path).get_run(err.value.summary["run_id"])
    assert run["status"] == "dq_failed" and run["failed"] == 6
    assert "gate_failures" in json.loads(run["notes"])


def test_few_parse_failures_pass_and_are_counted(db_path, make_zip):
    files = _files(["1", "2"])
    files["3"] = json.dumps({"info": {}}).encode()   # no innings
    s = ingest_zip(db_path, make_zip(files), "full")
    assert s["status"] == "success" and s["failed"] == 1 and s["added"] == 2
    notes = json.loads(_store(db_path).get_run(s["run_id"])["notes"])
    assert notes["failed_files"][0].startswith("3.json")


def test_large_active_drop_rolls_back(db_path, make_zip):
    ids = [str(i) for i in range(1, 101)]
    ingest_zip(db_path, make_zip(_files(ids)), "full")
    before = _snapshot(db_path)
    with pytest.raises(DataQualityError):
        ingest_zip(db_path, make_zip(_files(ids[:97])), "full")   # 3% drop
    assert _snapshot(db_path) == before


def test_runtime_error_rolls_back_and_records(db_path, make_zip, monkeypatch):
    ingest_zip(db_path, make_zip(_files(["1"])), "full")
    before = _snapshot(db_path)
    from db_logic.repository import raw_store

    def boom(self, *a):
        raise RuntimeError("disk on fire")
    monkeypatch.setattr(raw_store.RawStore, "mark_removed", boom)
    with pytest.raises(RuntimeError) as err:
        ingest_zip(db_path, make_zip(_files(["1", "2"])), "full")
    assert _snapshot(db_path) == before
    assert _store(db_path).get_run(err.value.summary["run_id"])["status"] == "error"


def test_nondigit_ids_are_stored_and_noted(db_path, make_zip):
    s = ingest_zip(db_path, make_zip(_files(["1", "abc_1"])), "full")
    assert s["added"] == 2 and s["nondigit_ids"] == 1
    notes = json.loads(_store(db_path).get_run(s["run_id"])["notes"])
    assert notes["nondigit_match_ids"] == ["abc_1"]


def test_only_non_json_members_fails_full(db_path, make_zip):
    with pytest.raises(DataQualityError):
        ingest_zip(db_path, make_zip({}), "full")
