"""Wikidata/Commons enrichment (P0.5): parsing, licence and age rules, and the service end to end
with a fake Wikimedia (no network)."""
import datetime
import io
import json
import os
import urllib.error
import urllib.parse

import pytest

from application_logic.services import enrich_service
from db_logic.loaders import wikimedia
from db_logic.repository.raw_store import RawStore, connect, migrate
from shared.config import get_config
from shared.exceptions import DownloadError

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
TODAY = datetime.date(2026, 10, 7)


def b(cid, item, **kw):
    """One SPARQL result row."""
    row = {"cid": {"value": cid}, "item": {"value": "http://www.wikidata.org/entity/" + item}}
    for k, v in kw.items():
        row[k] = {"value": v}
    return row


# ── loader ──────────────────────────────────────────────────────────────────────────────
def test_wikidata_date_precision():
    assert wikimedia.wikidata_date("+1988-11-05T00:00:00Z", "11") == "1988-11-05"
    assert wikimedia.wikidata_date("+1988-11-00T00:00:00Z", "10") == "1988-11"
    assert wikimedia.wikidata_date("+1988-00-00T00:00:00Z", "9") == "1988"
    assert wikimedia.wikidata_date("+1900-00-00T00:00:00Z", "8") is None     # decade
    assert wikimedia.wikidata_date("garbage", "11") is None


def test_parse_people_merges_rows_deterministically():
    img = "http://commons.wikimedia.org/wiki/Special:FilePath/Virat%20Kohli%202019.jpg"
    rows = [b("253802", "Q213854", label="Virat Kohli", dob="+1988-11-05T00:00:00Z", prec="11",
              bpLabel="Delhi", cfsLabel="India", img=img),
            b("253802", "Q999999999", label="Virat Kohli (duplicate)"),
            b("1", "Q5")]
    out = wikimedia.parse_people(rows)
    k = out["253802"]
    assert k["qid"] == "Q213854" and k["label_en"] == "Virat Kohli"
    assert (k["date_of_birth"], k["birthplace"], k["country_for_sport"]) == \
        ("1988-11-05", "Delhi", "India")
    assert k["image_file"] == "Virat Kohli 2019.jpg"
    assert out["1"] == {"qid": "Q5", "label_en": None, "date_of_birth": None, "birthplace": None,
                        "country_for_sport": None, "image_file": None}


def test_sparql_inlines_only_digit_ids():
    q = wikimedia.sparql_people(["253802", '1" } DROP', "x"])
    assert '"253802"' in q and "DROP" not in q and '"x"' not in q


@pytest.mark.parametrize("licence,ok", [
    ("Public domain", True), ("CC0", True), ("CC BY 2.0", True), ("CC BY-SA 4.0", True),
    ("CC BY-SA 3.0 de", True), ("CC BY-NC 2.0", False), ("CC BY-ND 4.0", False),
    ("CC BY-NC-SA 2.0", False), ("GFDL", False), (None, False)])
def test_licence_allowed(licence, ok):
    assert wikimedia.licence_allowed(licence) is ok


def imageinfo(name, licence="CC BY-SA 4.0", artist='<a href="//x">Jane <b>Doe</b></a>',
              thumb="https://upload.wikimedia.org/thumb/a.jpg/320px-a.jpg"):
    return {"title": "File:" + name, "imageinfo": [{
        "thumburl": thumb, "thumbwidth": 320, "thumbheight": 400,
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:" + name.replace(" ", "_"),
        "extmetadata": {"LicenseShortName": {"value": licence},
                        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
                        "Artist": {"value": artist}}}]}


def test_parse_imageinfo():
    doc = {"query": {"normalized": [{"from": "File:a_b.jpg", "to": "File:A b.jpg"}],
                     "pages": {"1": imageinfo("A b.jpg"),
                               "2": imageinfo("nc.jpg", licence="CC BY-NC 2.0"),
                               "-1": {"title": "File:gone.jpg", "missing": ""}}}}
    out = wikimedia.parse_imageinfo(doc)
    assert out["a_b.jpg"]["status"] == "ok" and out["a_b.jpg"]["author"] == "Jane Doe"
    assert out["nc.jpg"]["status"] == "rejected" and "CC BY-NC" in out["nc.jpg"]["note"]
    assert out["gone.jpg"]["status"] == "error"


class FakeResp(io.BytesIO):
    def __init__(self, data, ctype):
        super().__init__(data)
        self.headers = {"Content-Type": ctype}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_client_retries_429_then_succeeds_and_stops_on_404():
    calls, sleeps = [], []

    def opener(req, timeout):
        calls.append(req.get_header("User-agent"))
        if len(calls) == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "slow down", {"Retry-After": "7"}, None)
        return FakeResp(b'{"ok": 1}', "application/json")
    c = wikimedia.Client("ua/1 (contact)", opener=opener, sleep=sleeps.append, pause=1)
    assert c.json("https://example.org/x") == {"ok": 1}
    assert calls == ["ua/1 (contact)"] * 2 and 7.0 in sleeps

    def gone(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "nope", {}, None)
    c = wikimedia.Client("ua", opener=gone, sleep=lambda s: None)
    with pytest.raises(DownloadError):
        c.fetch("https://example.org/y")
    assert c.requests == 1


def test_thumbnail_checks_host_and_bytes():
    c = wikimedia.Client("ua", opener=lambda r, timeout: FakeResp(b"<svg/>", "image/jpeg"),
                         sleep=lambda s: None)
    with pytest.raises(DownloadError):
        wikimedia.fetch_thumbnail(c, "https://evil.example/x.jpg")
    with pytest.raises(DownloadError):
        wikimedia.fetch_thumbnail(c, "https://upload.wikimedia.org.evil.example/x.jpg")
    with pytest.raises(DownloadError):
        wikimedia.fetch_thumbnail(c, "http://upload.wikimedia.org/x.jpg")
    with pytest.raises(DownloadError):                       # says JPEG, isn't
        wikimedia.fetch_thumbnail(c, "https://upload.wikimedia.org/x.jpg")


def test_is_minor():
    assert enrich_service.is_minor("2010-01-01", TODAY)
    assert not enrich_service.is_minor("2008-10-07", TODAY)          # 18 today
    assert enrich_service.is_minor("2008-10-08", TODAY)
    assert enrich_service.is_minor("2008", TODAY)                    # year only: latest birthday
    assert not enrich_service.is_minor("2007", TODAY)
    assert not enrich_service.is_minor(None, TODAY)


# ── service ─────────────────────────────────────────────────────────────────────────────
class FakeWikimedia:
    """Routes the three kinds of request a run makes."""

    def __init__(self, people, images, fail_sparql=False):
        self.people, self.images, self.fail_sparql = people, images, fail_sparql
        self.log = []

    def __call__(self, req, timeout):
        url = req.full_url
        self.log.append(url.split("?")[0])
        if url.startswith(wikimedia.SPARQL_URL):
            if self.fail_sparql:
                raise urllib.error.HTTPError(url, 500, "down", {}, None)
            q = urllib.parse.parse_qs(req.data.decode())["query"][0]
            rows = [r for r in self.people if '"%s"' % r["cid"]["value"] in q]
            return FakeResp(json.dumps({"results": {"bindings": rows}}).encode(),
                            "application/sparql-results+json")
        if url.startswith(wikimedia.COMMONS_API):
            titles = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["titles"][0]
            pages = {str(i): self.images[t[5:]] for i, t in enumerate(titles.split("|"))
                     if t[5:] in self.images}
            return FakeResp(json.dumps({"query": {"pages": pages}}).encode(), "application/json")
        return FakeResp(JPEG, "image/jpeg")


@pytest.fixture
def env(cricstat_env, monkeypatch):
    monkeypatch.setenv("CRICSTAT_ENRICH_BATCH", "2")
    cfg = get_config(reload=True)
    conn = connect(cfg.RAW_DB)
    migrate(conn, "2026-10-01T00:00:00Z")
    store = RawStore(conn)
    store.begin()
    store.replace_register([
        ("ba607b88", "V Kohli", "V Kohli", json.dumps({"cricinfo": ["253802"]})),
        ("5d2eda89", "S Mandhana", "S Mandhana", json.dumps({"cricinfo": ["597806"]})),
        ("aaaaaaaa", "Y Teen", "Y Teen", json.dumps({"cricinfo": ["111"]})),
        ("bbbbbbbb", "N Obody", "N Obody", json.dumps({"cricinfo": ["222"]})),
        ("cccccccc", "N Ocricinfo", "N Ocricinfo", json.dumps({}))], [])
    store.commit()
    conn.close()
    return cfg


def fake_world():
    path = "http://commons.wikimedia.org/wiki/Special:FilePath/"
    people = [b("253802", "Q213854", label="Virat Kohli", img=path + "Kohli.jpg",
                dob="+1988-11-05T00:00:00Z", prec="11"),
              b("597806", "Q2", label="Smriti Mandhana", img=path + "Mandhana%20nc.jpg"),
              b("111", "Q3", label="Young Teen", img=path + "Teen.jpg",
                dob="+2010-03-01T00:00:00Z", prec="11")]
    images = {"Kohli.jpg": imageinfo("Kohli.jpg"),
              "Mandhana nc.jpg": imageinfo("Mandhana nc.jpg", licence="CC BY-NC 2.0"),
              "Teen.jpg": imageinfo("Teen.jpg")}
    return people, images


def client(fake):
    return wikimedia.Client("ua (contact)", opener=fake, sleep=lambda s: None, pause=0)


def test_enrich_end_to_end(env):
    fake = FakeWikimedia(*fake_world())
    s = enrich_service.run(env, client(fake), today=TODAY)
    assert s["status"] == "success"
    assert (s["ids"], s["due"], s["looked_up"], s["on_wikidata"]) == (4, 4, 4, 3)
    assert (s["photos_ok"], s["photos_rejected"], s["photos_skipped_minor"]) == (1, 1, 1)
    store = RawStore(connect(env.RAW_DB))
    people = store.wikidata_people()
    assert people["253802"]["label_en"] == "Virat Kohli"
    assert people["222"]["qid"] is None                         # looked up, not on Wikidata
    imgs = store.commons_images()
    assert "Teen.jpg" not in imgs                               # a minor's photo isn't fetched
    ok = imgs["Kohli.jpg"]
    assert ok["status"] == "ok" and ok["author"] == "Jane Doe" and ok["licence"] == "CC BY-SA 4.0"
    with open(os.path.join(env.PHOTO_DIR, ok["thumb_path"]), "rb") as f:
        assert f.read() == JPEG
    nc = imgs["Mandhana nc.jpg"]
    assert nc["status"] == "rejected" and nc["thumb_path"] is None
    run = store.latest_run(("enrich",))
    assert run["status"] == "success" and json.loads(run["notes"])["photos_ok"] == 1

    again = FakeWikimedia(*fake_world())                        # nothing is due a day later
    s = enrich_service.run(env, client(again), today=TODAY)
    assert (s["due"], s["photos_due"]) == (0, 0) and again.log == []


def test_enrich_failure_is_logged_and_keeps_finished_batches(env):
    fake = FakeWikimedia(*fake_world(), fail_sparql=True)
    with pytest.raises(DownloadError) as exc:
        enrich_service.run(env, client(fake), today=TODAY)
    assert exc.value.summary["status"] == "error"
    store = RawStore(connect(env.RAW_DB))
    runs = store.conn.execute("SELECT status FROM ingest_runs WHERE mode = 'enrich'").fetchall()
    assert runs == [("error",)]
