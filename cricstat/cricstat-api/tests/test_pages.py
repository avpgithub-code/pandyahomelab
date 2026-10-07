"""Server-rendered player/team page heads and the sitemap (P0.6), against the fixture DB and the
real page shells in cricstat/web (so a shell edit that drops a marker fails here)."""
import json
import os
import re
import xml.etree.ElementTree as ET

import pytest

from application_logic.services.slugs import full_name
from tests.conftest import CRICSTAT, pid

KOHLI = pid("V Kohli")
WEB = str(CRICSTAT / "web")


def make_client(home, monkeypatch, **env):
    from fastapi.testclient import TestClient

    from presentation_logic.api.app import create_app
    from shared.config import Config

    monkeypatch.setenv("CRICSTAT_HOME", str(home))
    monkeypatch.setenv("CRICSTAT_WEB_DIR", WEB)
    for k in ("CRICSTAT_INDEX_MIN_INTL", "CRICSTAT_INDEX_MIN_LEAGUE"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return TestClient(create_app(Config()))


@pytest.fixture()
def strict(home, monkeypatch):            # production thresholds: the fixture players are thin
    with make_client(home, monkeypatch) as c:
        yield c


@pytest.fixture()
def lenient(home, monkeypatch):           # low thresholds, so fixture players count as indexable
    with make_client(home, monkeypatch, CRICSTAT_INDEX_MIN_INTL="3",
                     CRICSTAT_INDEX_MIN_LEAGUE="1") as c:
        yield c


def head(html, pattern):
    m = re.search(pattern, html, re.S)
    return m.group(1) if m else None


def ld(html):
    return json.loads(head(html, r'<script type="application/ld\+json">(.*?)</script>'))


def test_full_name():
    assert full_name("V Kohli", ["Kohli", "Virat Kohli"]) == "Virat Kohli"
    assert full_name("MS Dhoni", ["M.S. Dhoni", "Mahendra Singh Dhoni"]) == "Mahendra Singh Dhoni"
    assert full_name("PD Salt", ["P Salt", "Philip Salt", "Philip Dean Salt"]) == "Philip Salt"
    assert full_name("Rashid Khan", ["R Khan"]) == "Rashid Khan"
    assert full_name("S Mandhana", []) == "S Mandhana"           # no variant: scorecard name
    assert full_name("V Kohli", ["Virat Singh"]) == "V Kohli"      # another surname is ignored


def test_player_page(lenient):
    r = lenient.get("/pages/players/v-kohli-%s/" % KOHLI)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    h = r.text
    assert head(h, r"<title>(.*?)</title>").startswith("V Kohli — ODI, T20I &amp; Test stats")
    assert head(h, r'<link rel="canonical" href="([^"]*)"') == \
        "https://pandyahomelab.com/cricket/players/v-kohli-%s/" % KOHLI
    assert head(h, r'<meta name="robots" content="([^"]*)"') == "index,follow"
    desc = head(h, r'<meta name="description" content="([^"]*)"')
    assert desc.startswith("V Kohli (India, ") and "ODIs" in desc
    assert head(h, r'<meta property="og:type" content="([^"]*)"') == "profile"
    data = ld(h)
    assert data["@type"] == "ProfilePage" and data["mainEntity"]["name"] == "V Kohli"
    assert data["mainEntity"]["memberOf"]["name"] == "India"
    summary = head(h, r'<div id="p-profile" aria-live="polite">(.*?)</div>\s*</main>')
    assert "<h1>V Kohli" in summary
    assert '<a href="/cricket/countries/india-men/">India</a>' in summary
    assert ">ODI<" in summary and ">IPL<" in summary
    assert h.count("<div") == h.count("</div>")


def test_thin_player_is_noindex(strict):
    h = strict.get("/pages/players/v-kohli-%s/" % KOHLI).text
    assert head(h, r'<meta name="robots" content="([^"]*)"') == "noindex,follow"


def test_player_redirect_and_not_found(strict):
    r = strict.get("/pages/players/virat-kohli-%s/" % KOHLI, follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == "/cricket/players/v-kohli-%s/" % KOHLI
    for slug in ("nobody-00000000", "no-id-here", "x"):
        r = strict.get("/pages/players/%s/" % slug)
        assert r.status_code == 404, slug
        assert head(r.text, r'<meta name="robots" content="([^"]*)"') == "noindex"
        assert 'rel="canonical"' not in r.text and "og:url" not in r.text


def test_team_pages(lenient):
    h = lenient.get("/pages/countries/india-men/").text
    assert head(h, r"<title>(.*?)</title>") == \
        "India men&#x27;s cricket team — ODI, T20I &amp; Test record &amp; results | cricstat"
    assert head(h, r'<meta name="robots" content="([^"]*)"') == "index,follow"
    assert '<h1 id="c-name" style="font-size:clamp(2rem,5vw,3rem);margin:0">India men</h1>' in h
    assert "skeleton" not in h and ">Win %<" in h and h.count("<div") == h.count("</div>")
    assert ld(h)["@type"] == "SportsTeam"
    club = lenient.get("/pages/countries/mumbai-indians-men/").text
    assert head(club, r'<meta name="robots" content="([^"]*)"') == "noindex,follow"
    assert lenient.get("/pages/countries/nowhere-men/").status_code == 404


def test_sitemap(lenient, strict):
    r = lenient.get("/pages/sitemap.xml")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text for e in ET.fromstring(r.content).findall("s:url/s:loc", ns)]
    base = "https://pandyahomelab.com/cricket/"
    assert base + "players/v-kohli-%s/" % KOHLI in locs
    assert base + "countries/india-men/" in locs
    assert not any("mumbai-indians" in u for u in locs)            # clubs aren't indexed yet
    assert ET.fromstring(strict.get("/pages/sitemap.xml").content).findall("s:url", ns) == []


def test_etag_and_missing_shell(lenient, home, monkeypatch):
    url = "/pages/players/v-kohli-%s/" % KOHLI
    tag = lenient.get(url).headers["etag"]
    assert lenient.get(url, headers={"If-None-Match": tag}).status_code == 304
    with make_client(home, monkeypatch, CRICSTAT_WEB_DIR=os.path.join(str(home), "no-web")) as c:
        assert c.get(url).status_code == 503                     # Nginx then serves the shell
