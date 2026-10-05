"""Pytest configuration — puts the service root on sys.path so the symlinked
db_logic / application_logic / presentation_logic packages resolve.

Fixtures build tiny Cricsheet-shaped match files and zip them in tmp_path; no test
touches the network or the real data/ folder.
"""
import json
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def match_bytes(match_id, match_type="T20", gender="male", team_type="international",
                dates=("2026-09-10",), teams=("India", "Australia"), event="Test Series",
                revision=1, runs=0):
    """A minimal match file in Cricsheet's JSON layout (meta / info / innings)."""
    doc = {
        "meta": {"data_version": "1.2.0", "created": "2026-09-16", "revision": revision},
        "info": {
            "dates": list(dates), "gender": gender, "match_type": match_type,
            "team_type": team_type, "teams": list(teams),
            "outcome": {"winner": teams[0]},
        },
        "innings": [{"team": teams[0], "overs": [{"over": 0, "deliveries": [
            {"batter": "A", "bowler": "B", "non_striker": "C",
             "runs": {"batter": runs, "extras": 0, "total": runs}}]}]}],
    }
    if event is not None:
        doc["info"]["event"] = {"name": event}
    # Cricsheet files are indented JSON; the exact bytes are what gets hashed.
    return json.dumps(doc, indent=2).encode("utf-8")


def write_zip(path, files, readme=True):
    """files: {name_or_match_id: bytes}. Bare ids get a .json suffix."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        if readme:
            zf.writestr("README.txt", "This zip archive contains data files from Cricsheet.")
        for name, raw in files.items():
            zf.writestr(name if "." in name else name + ".json", raw)
    return str(path)


@pytest.fixture
def make_zip(tmp_path):
    counter = {"n": 0}

    def _make(files, readme=True):
        counter["n"] += 1
        return write_zip(tmp_path / ("src%d.zip" % counter["n"]), files, readme)
    return _make


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "db" / "raw.sqlite")


@pytest.fixture
def cricstat_env(tmp_path, monkeypatch):
    """Point every CRICSTAT_* path at tmp_path."""
    for key in list(os.environ):
        if key.startswith("CRICSTAT_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("CRICSTAT_HOME", str(tmp_path / "home"))
    return tmp_path / "home"
