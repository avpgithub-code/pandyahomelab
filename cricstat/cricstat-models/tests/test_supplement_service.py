"""Draft → weekly check, offline: a fake Wikipedia with one season page, one series article and the
team article. Covers the second-source check, the checksum table, carry-over of a reviewer's
'accepted' and the proposal diff (the check never edits the committed files)."""
import datetime

from application_logic.services import supplement_service as svc
from db_logic.repository import supplement_store as store
from tests.conftest import make_serving_db

SEASON = """
==March==
===Afghanistan in Ireland===
{{main|Afghan cricket team in Ireland in 2018}}
{| class="wikitable"
|-
! No.
! Date
! Home captain
! Away captain
! Venue
! Result
|-
| [http://x/ci/engine/match/900001.html ODI 4000] || 1 March || a || b || [[Ground]], [[Dublin]] || {{cr|AFG|2013}} by 5 wickets
|-
| [http://x/ci/engine/match/900002.html ODI 4001] || 3 March || a || b || [[Ground]], [[Dublin]] || {{cr|IRE}} by 2 runs
|}
"""
SERIES = """
{{Single-innings cricket match
| date = 1 March 2018
| team1 = {{cr-rt|IRE}}
| team2 = {{cr|AFG}}
| result = Afghanistan won by 5 wickets
| report = [http://x/ci/engine/match/900001.html Scorecard]
}}
"""
TEAM = """
====ODI record versus other nations====
{| class="wikitable"
|-
!scope=row |{{cr|Ireland}}
| 2 || 1 || 1 || 0 || 0 || 50.00 || 2018 || 2018
|- class="sortbottom"
!scope="row" style="text-align:center" |'''Total'''
|'''2'''||'''1'''||'''1'''||'''0'''||'''0'''||'''50.00'''||'''2018'''||'''2018'''
|-
|colspan=10|{{small|''Statistics are correct as of {{cr|AFG}} v {{cr|IRE}} at [[Ground]]; 3 March 2018''}}<ref>x</ref>
|}
"""


class FakeWiki:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def page(self, title):
        self.calls.append(title)
        if title in self.pages:
            return {"title": title, "revid": 7, "wikitext": self.pages[title]}
        return {"title": title, "revid": None, "wikitext": "", "missing": True}

    def search_title(self, *a, **k):
        return None


def _wiki(season=SEASON):
    return FakeWiki({"International cricket in 2018": season,
                     "Afghan cricket team in Ireland in 2018": SERIES,
                     svc.TEAM_ARTICLE: TEAM})


def _draft(cfg, tmp_path, wiki):
    make_serving_db(cfg.SERVING_DB, [])
    return svc.draft(cfg, out_dir=str(tmp_path / "out"), client=wiki,
                     today=datetime.date(2018, 12, 31))


def test_draft_rows_second_source_and_checksum(cfg, tmp_path):
    rep = _draft(cfg, tmp_path, _wiki())
    rows = store.read_results(str(tmp_path / "out"))
    assert [(r["match_key"], r["team1"], r["team2"], r["winner"], r["venue_country"],
             r["check_status"]) for r in rows] == [
        ("900001", "Afghanistan", "Ireland", "Afghanistan", "Ireland", "confirmed"),
        ("900002", "Afghanistan", "Ireland", "Ireland", "Ireland", "not_found")]
    assert rep["totals_errors"] == [] and rep["issues"] == []
    totals = store.read_totals(str(tmp_path / "out"))
    assert totals[-1]["opponent"] == "TOTAL" and totals[-1]["as_of"].endswith("3 March 2018")


def _review(cfg, *rows):
    import csv
    with open("%s/%s" % (cfg.SUPPLEMENT_DIR, store.REVIEWS_FILE), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["match_key", "field", "value", "wikipedia_value", "note", "reviewed_on"])
        w.writerows(rows)


def test_reviews_are_applied_on_every_draft(cfg, tmp_path):
    _review(cfg, ["900002", "start_date", "2018-03-04", "2018-03-03", "box says 4 March", "x"])
    rep = _draft(cfg, tmp_path, _wiki())
    r = store.read_results(str(tmp_path / "out"))[1]
    assert (r["start_date"], r["check_status"], r["note"]) == ("2018-03-04", "accepted",
                                                                "box says 4 March")
    assert rep["issues"] == []
    # Wikipedia later changes the overruled value: the row is flagged, not silently corrected.
    moved = SEASON.replace("| 3 March ||", "| 5 March ||")
    rep = _draft(cfg, tmp_path, _wiki(moved))
    r = store.read_results(str(tmp_path / "out"))[1]
    assert r["check_status"] == "differs" and "Wikipedia now says" in rep["issues"][0]


def test_check_proposes_but_never_edits(cfg, tmp_path):
    _review(cfg, ["900002", "", "", "", "checked the scorecard by hand", "x"])
    _draft(cfg, tmp_path, _wiki())
    rows = store.read_results(str(tmp_path / "out"))
    assert rows[1]["check_status"] == "accepted"
    store.write_results(cfg.SUPPLEMENT_DIR, rows)
    store.write_totals(cfg.SUPPLEMENT_DIR, store.read_totals(str(tmp_path / "out")))
    before = open("%s/%s" % (cfg.SUPPLEMENT_DIR, store.RESULTS_FILE)).read()

    same = svc.propose(cfg, client=_wiki())
    assert same["up_to_date"] is True

    changed_season = SEASON.replace("{{cr|IRE}} by 2 runs", "{{cr|AFG|2013}} by 2 runs")
    prop = svc.propose(cfg, client=_wiki(changed_season))
    assert prop["up_to_date"] is False
    assert prop["changed"][0]["match_key"] == "900002"
    assert prop["changed"][0]["now"]["winner"] == "Afghanistan"
    assert open("%s/%s" % (cfg.SUPPLEMENT_DIR, store.RESULTS_FILE)).read() == before
