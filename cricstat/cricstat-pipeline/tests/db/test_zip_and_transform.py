"""Tests for db-logic loaders/transforms — reading from the zip, building records."""
import json
import zipfile

import pytest

from db_logic.loaders.cricsheet_zip import CricsheetZip
from db_logic.transforms.match_record import (
    MatchParseError,
    build_record,
    decompress,
    sha256_hex,
)
from shared.exceptions import SourceError
from tests.conftest import match_bytes


def test_reads_json_members_and_skips_others(make_zip, tmp_path):
    path = make_zip({"1001": match_bytes("1001"), "notes.md": b"# hi", "1002": match_bytes("1002")})
    zf = CricsheetZip(path)
    ids = [m.match_id for m in zf]
    assert ids == ["1001", "1002"]
    assert sorted(zf.skipped) == ["README.txt", "notes.md"]
    assert not list(tmp_path.glob("*.json"))  # nothing extracted to disk


def test_nested_paths_use_file_stem(tmp_path):
    path = tmp_path / "n.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("json/2001.json", match_bytes("2001"))
    assert [m.match_id for m in CricsheetZip(str(path))] == ["2001"]


def test_not_a_zip_or_missing(tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(SourceError):
        CricsheetZip(str(bad))
    with pytest.raises(SourceError):
        CricsheetZip(str(tmp_path / "missing.zip"))


def test_build_record_extracts_metadata_and_keeps_exact_bytes():
    raw = match_bytes("1", match_type="ODI", gender="female", team_type="club",
                      dates=("2026-01-03", "2026-01-02"), teams=("Kent", "Essex"),
                      event="County Cup", revision=3)
    rec = build_record("1", raw)
    assert rec["match_type"] == "ODI"
    assert rec["gender"] == "female"
    assert rec["team_type"] == "club"
    assert rec["start_date"] == "2026-01-02"
    assert json.loads(rec["teams"]) == ["Kent", "Essex"]
    assert rec["event_name"] == "County Cup"
    assert rec["revision"] == 3 and rec["data_version"] == "1.2.0"
    assert decompress(rec["json_zlib"]) == raw
    assert rec["sha256"] == sha256_hex(raw) and rec["json_bytes"] == len(raw)


def test_build_record_without_event():
    assert build_record("1", match_bytes("1", event=None))["event_name"] is None


@pytest.mark.parametrize("raw", [b"{not json", b"[1, 2]", b'{"info": {}}',
                                 b'{"innings": []}', b"\xff\xfe", b'{"info": 1, "innings": []}'])
def test_build_record_rejects_bad_files(raw):
    with pytest.raises(MatchParseError):
        build_record("1", raw)
