"""Tests for presentation-logic/cli — JSON summary on stdout, exit codes, log file."""
import json
import os

from presentation_logic.cli.main import main
from tests.conftest import match_bytes


def _last_json(capsys):
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1          # stdout is exactly one JSON line
    return json.loads(out[0])


def test_zip_path_run_exit_0_and_log(cricstat_env, make_zip, capsys):
    path = make_zip({"1": match_bytes("1"), "2": match_bytes("2")})
    assert main(["full", "--zip-path", path, "--quiet"]) == 0
    s = _last_json(capsys)
    assert s["status"] == "success" and s["added"] == 2 and s["exit_code"] == 0
    assert "duration_s" in s and s["mode"] == "full"
    assert os.path.isfile(cricstat_env / "data" / "db" / "raw.sqlite")
    logs = os.listdir(cricstat_env / "logs")
    assert len(logs) == 1 and logs[0].startswith("ingest-") and logs[0].endswith(".log")


def test_dq_failure_exit_2(cricstat_env, make_zip, capsys):
    path = make_zip({str(i): b"nope" for i in range(10)})
    assert main(["recent", "--zip-path", path, "--quiet"]) == 2
    s = _last_json(capsys)
    assert s["status"] == "dq_failed" and s["gate_failures"]


def test_missing_zip_exit_1(cricstat_env, tmp_path, capsys):
    assert main(["full", "--zip-path", str(tmp_path / "nope.zip"), "--quiet"]) == 1
    s = _last_json(capsys)
    assert s["status"] == "error" and "SourceError" in s["error"]


def test_download_path_is_mocked(cricstat_env, make_zip, monkeypatch, capsys):
    from db_logic.loaders import downloader
    src = make_zip({"7": match_bytes("7")})
    calls = []

    def fake_download(url, dest_dir, ua, **kw):
        calls.append((url, ua))
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, downloader.dated_name(url))
        with open(src, "rb") as a, open(dest, "wb") as b:
            b.write(a.read())
        return dest
    monkeypatch.setattr(downloader, "download", fake_download)
    assert main(["recent", "--quiet"]) == 0
    s = _last_json(capsys)
    assert calls[0][0].endswith("recently_added_7_json.zip")
    assert "cricstat/0.1" in calls[0][1]
    assert s["source"] == calls[0][0] and s["added"] == 1
