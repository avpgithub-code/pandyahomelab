"""Tests for db-logic/loaders/downloader — mocked HTTP, retries, atomic rename, pruning."""
import io
import os
import urllib.error

import pytest

from db_logic.loaders import downloader
from shared.exceptions import DownloadError
from tests.conftest import match_bytes, write_zip

URL = "https://cricsheet.org/downloads/all_json.zip"
UA = "cricstat/0.1 (+https://pandyahomelab.com/cricket/)"


class FakeResponse(io.BytesIO):
    def __init__(self, data, length=None):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data) if length is None else length)}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


@pytest.fixture
def zip_bytes(tmp_path):
    path = write_zip(tmp_path / "payload.zip", {"1": match_bytes("1")})
    with open(path, "rb") as f:
        return f.read()


def test_download_sets_user_agent_and_renames(tmp_path, zip_bytes):
    seen = {}

    def opener(req, timeout):
        seen["ua"] = req.get_header("User-agent")
        seen["timeout"] = timeout
        return FakeResponse(zip_bytes)

    dest = tmp_path / "raw"
    path = downloader.download(URL, str(dest), UA, timeout=12, opener=opener, stamp="20261005")
    assert path == str(dest / "all_json-20261005.zip")
    assert seen == {"ua": UA, "timeout": 12}
    assert os.listdir(dest) == ["all_json-20261005.zip"]  # no .part left behind


def test_download_retries_with_backoff(tmp_path, zip_bytes):
    calls, sleeps = [], []

    def opener(req, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.URLError("connection reset")
        return FakeResponse(zip_bytes)

    downloader.download(URL, str(tmp_path), UA, retries=4, backoff=2, opener=opener,
                        sleep=sleeps.append, stamp="20261005")
    assert len(calls) == 3 and sleeps == [2, 4]


def test_download_gives_up_and_cleans_part(tmp_path):
    def opener(req, timeout):
        return FakeResponse(b"<html>not a zip</html>")

    with pytest.raises(DownloadError):
        downloader.download(URL, str(tmp_path), UA, retries=1, backoff=0, opener=opener,
                            sleep=lambda s: None, stamp="20261005")
    assert os.listdir(tmp_path) == []


def test_short_read_is_retried(tmp_path, zip_bytes):
    responses = [FakeResponse(zip_bytes[:10], length=len(zip_bytes)), FakeResponse(zip_bytes)]
    path = downloader.download(URL, str(tmp_path), UA, retries=2, backoff=0,
                               opener=lambda r, timeout: responses.pop(0),
                               sleep=lambda s: None, stamp="20261005")
    assert os.path.getsize(path) == len(zip_bytes)


def test_http_404_not_retried(tmp_path):
    calls = []

    def opener(req, timeout):
        calls.append(1)
        raise urllib.error.HTTPError(URL, 404, "Not Found", {}, None)

    with pytest.raises(DownloadError):
        downloader.download(URL, str(tmp_path), UA, retries=3, opener=opener,
                            sleep=lambda s: None)
    assert len(calls) == 1


def test_prune_keeps_newest(tmp_path):
    for d in ("20260901", "20261001", "20260801", "20260701"):
        (tmp_path / ("all_json-%s.zip" % d)).write_bytes(b"x")
    (tmp_path / "recently_added_7_json-20261001.zip").write_bytes(b"x")
    removed = downloader.prune(str(tmp_path), URL, keep=3)
    assert [os.path.basename(p) for p in removed] == ["all_json-20260701.zip"]
    assert sorted(os.listdir(tmp_path)) == [
        "all_json-20260801.zip", "all_json-20260901.zip", "all_json-20261001.zip",
        "recently_added_7_json-20261001.zip"]
