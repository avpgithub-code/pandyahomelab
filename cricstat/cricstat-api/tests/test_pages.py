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
WEB = os.environ.get("CRICSTAT_TEST_WEB", str(CRICSTAT / "web"))


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


def test_player_page_hides_the_players_intro(lenient):
    """P1.6 shell: the Players intro (heading, seal, count) shows only on the plain Players page."""
    if 'id="p-intro"' not in open(os.path.join(WEB, "players", "index.html")).read():
        return                                  # older shell, before the intro existed
    h = lenient.get("/pages/players/v-kohli-%s/" % KOHLI).text
    assert 'id="p-intro" hidden' in h


def test_team_pages(lenient):
    h = lenient.get("/pages/countries/india-men/").text
    assert head(h, r"<title>(.*?)</title>") == \
        "India men&#x27;s cricket team — ODI, T20I &amp; Test record &amp; results | cricstat"
    assert head(h, r'<meta name="robots" content="([^"]*)"') == "index,follow"
    assert '<h1 id="c-name" style="font-size:clamp(2rem,5vw,3rem);margin:0">India men</h1>' in h
    assert "skeleton" not in h and ">Win %<" in h and h.count("<div") == h.count("</div>")
    assert ld(h)["@type"] == "SportsTeam"
    if 'id="c-landing"' in open(os.path.join(WEB, "countries", "index.html")).read():
        # P1.6 shell: the static page is the world-map landing; a team page shows the team header
        assert '<div id="c-landing" hidden' in h and 'id="c-hero">' in h
        assert 'id="c-hero" hidden' not in h
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


# ── P0.5: Wikidata name, birth details and Commons photo ──────────────────────────────────
@pytest.fixture()
def with_bio(home, tmp_path, monkeypatch):
    """A copy of the fixture DB where Kohli has a player_bio row, as a build after `enrich`
    leaves it."""
    import shutil
    import sqlite3

    h = tmp_path / "home"
    (h / "data" / "db").mkdir(parents=True)
    shutil.copy(str(home / "data" / "db" / "cricstat.sqlite"), str(h / "data" / "db"))
    c = sqlite3.connect(str(h / "data" / "db" / "cricstat.sqlite"))
    key = c.execute("SELECT player_key FROM players WHERE player_id = ?", (KOHLI,)).fetchone()[0]
    c.execute("INSERT INTO player_bio (player_key, wikidata_qid, date_of_birth, birthplace,"
              " country_for_sport, full_name, photo_file, photo_width, photo_height,"
              " photo_licence, photo_licence_url, photo_author, photo_source_url)"
              " VALUES (?, 'Q213854', '1988-11-05', 'Delhi', 'India', 'Virat Kohli', 'ab12.jpg',"
              " 320, 400, 'CC BY-SA 4.0', 'https://creativecommons.org/licenses/by-sa/4.0',"
              " 'Jane <Doe>', 'https://commons.wikimedia.org/wiki/File:K.jpg')", (key,))
    c.execute("INSERT INTO player_names VALUES (?, 'Virat Kohli', 'wikidata')", (key,))
    c.commit()
    c.close()
    with make_client(h, monkeypatch, CRICSTAT_INDEX_MIN_INTL="3") as client:
        yield client


def test_full_name_prefers_wikidata():
    assert full_name("S Mandhana", [], "Smriti Mandhana") == "Smriti Mandhana"
    assert full_name("V Kohli", ["Virat Kohli"], "Wrong Person") == "Virat Kohli"   # surname
    assert full_name("MS Dhoni", ["Mahendra Singh Dhoni"], "MS Dhoni") == "Mahendra Singh Dhoni"
    assert full_name("Babar Azam", [], "Mohammad Babar Azam") == "Babar Azam"   # already full
    assert full_name("F du Plessis", [], "Faf du Plessis") == "Faf du Plessis"


def test_profile_has_bio_and_photo(with_bio):
    p = with_bio.get("/v1/players/%s" % KOHLI).json()["data"]
    assert p["full_name"] == "Virat Kohli"
    assert p["bio"]["date_of_birth"] == "1988-11-05" and p["bio"]["source"] == "Wikidata (CC0)"
    assert p["photo"]["url"] == "/cricket/photos/ab12.jpg" and p["photo"]["author"] == "Jane <Doe>"
    assert with_bio.get("/v1/players/%s" % pid("AusM 2")).json()["data"].get("photo") is None


def test_page_uses_name_birth_and_photo(with_bio):
    h = with_bio.get("/pages/players/v-kohli-%s/" % KOHLI).text
    assert head(h, r"<title>(.*?)</title>").startswith("Virat Kohli — ")
    assert head(h, r'<meta property="og:image" content="([^"]*)"') == \
        "https://pandyahomelab.com/cricket/photos/ab12.jpg"
    assert head(h, r'<meta name="twitter:card" content="([^"]*)"') == "summary"
    assert "Born 5 November 1988, Delhi" in h
    assert "Photo: Jane &lt;Doe&gt;, " in h and "Jane <Doe>" not in h          # escaped
    person = ld(h)["mainEntity"]
    assert person["birthDate"] == "1988-11-05" and person["birthPlace"]["name"] == "Delhi"
    assert person["image"] == "https://pandyahomelab.com/cricket/photos/ab12.jpg"
    assert person["sameAs"] == ["https://www.wikidata.org/wiki/Q213854"]


def test_godl_photo_credit_says_no_endorsement(with_bio):
    import sqlite3

    from shared.config import Config
    c = sqlite3.connect(Config().SERVING_DB)
    c.execute("UPDATE player_bio SET photo_licence = 'GODL-India'")
    c.commit()
    c.close()
    h = with_bio.get("/pages/players/v-kohli-%s/" % KOHLI).text
    assert "GODL-India</a>, via" in h and "No endorsement by the Government of India" in h


def test_search_finds_wikidata_name_and_returns_photo(with_bio):
    players = with_bio.get("/v1/search?type=player&q=Virat").json()["data"]["players"]
    assert [p["name"] for p in players] == ["V Kohli"]
    assert players[0]["full_name"] == "Virat Kohli"
    assert players[0]["photo_url"] == "/cricket/photos/ab12.jpg"
    other = with_bio.get("/v1/search", params={"type": "player", "q": "AusM"}).json()
    other = other["data"]["players"][0]
    assert other["full_name"] == other["name"] and other["photo_url"] is None


def test_one_word_search_ranks_by_career_not_by_alias(with_bio):
    """A one-word Register variant equal to the query is not an 'exact' hit: careers decide."""
    import sqlite3

    from shared.config import Config
    c = sqlite3.connect(Config().SERVING_DB)
    small = c.execute("SELECT p.player_key FROM players p JOIN player_career pc USING (player_key)"
                      " WHERE pc.scope = 'ALL' AND p.player_id != ? ORDER BY pc.matches LIMIT 1",
                      (KOHLI,)).fetchone()[0]
    c.execute("INSERT INTO player_names VALUES (?, 'Kohli', 'register_variant')", (small,))
    c.commit()
    c.close()
    names = [p["name"] for p in with_bio.get("/v1/search", params={
        "type": "player", "q": "Kohli"}).json()["data"]["players"]]
    assert names[0] == "V Kohli" and len(names) == 2
    exact = with_bio.get("/v1/search", params={"type": "player", "q": "Virat Kohli"}).json()
    assert exact["data"]["players"][0]["match"] == "exact"



def test_leaders_and_top_players_carry_full_name_and_photo(with_bio):
    rows = with_bio.get("/v1/leaderboards/batting", params={"scope": "ODI"}).json()["data"]
    kohli = next(r for r in rows if r["player_id"] == KOHLI)
    assert kohli["full_name"] == "Virat Kohli" and kohli["photo_url"] == "/cricket/photos/ab12.jpg"
    assert all("full_name" in r and "photo_url" in r for r in rows)
    top = with_bio.get("/v1/teams/india-men/top-players", params={"metric": "runs"}).json()["data"]
    kohli = next(r for r in top if r["player_id"] == KOHLI)
    assert kohli["full_name"] == "Virat Kohli" and kohli["photo_url"] == "/cricket/photos/ab12.jpg"
