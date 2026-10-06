"""cricstat golden review (P0.3b): pure parts only — no network, no Postgres."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.cricstat import golden, wiki  # noqa: E402

INFOBOX = """{{Infobox cricketer
| name = Test Player
| columns = 3
| column1 = [[Women's Test cricket|WTest]]
| matches1 = 9
| runs1 = 1,788<ref>x</ref>
| bat avg1 = 52.53
| 100s/50s1 = 2/5
| top score1 = 149*
| wickets1 = 0
| bowl avg1 = –
| fivefor1 = –
| best bowling1 = –
| catches/stumpings1 = 3/–
| column2 = [[Women's One Day International|WODI]]
| matches2 = 120
| best bowling2 = 1/13
| catches/stumpings2 = 43/2
| column3 = [[List A cricket|LA]]
| matches3 = 200
| date = 22 September
| source = http://www.espncricinfo.com/
}}"""


def test_parse_infobox_maps_women_columns_and_cleans_values():
    p = wiki.parse_infobox(INFOBOX)
    assert set(p["scopes"]) == {"TEST", "ODI"}                    # List A is not a golden scope
    t = p["scopes"]["TEST"]
    assert (t["Mat"], t["Runs"], t["HS"], t["100"], t["Ct"], t["St"]) == \
        ("9", "1788", "149*", "2", "3", "-")
    assert t["Bowl Ave"] == "-" and p["scopes"]["ODI"]["BBI"] == "1/13"
    assert p["scopes"]["ODI"]["St"] == "2"


def test_as_of_without_a_year_is_the_most_recent_such_date():
    assert wiki._as_of("22 September", datetime(2026, 10, 6)) == "2026-09-22"
    assert wiki._as_of("22 November", datetime(2026, 10, 6)) == "2025-11-22"
    assert wiki._as_of("5 October 2026") == "2026-10-05"


def _blocks():
    return [{"kind": "player", "id": "p1", "name": "P One", "scope": "TEST", "mat": "10",
             "window": "career", "rows": [{"metric": "Mat", "ours": "10"},
                                          {"metric": "Runs", "ours": "500"},
                                          {"metric": "HS", "ours": "94"}]}]


def test_merge_status_and_summary():
    refs = {("p1", "TEST", "Mat"): {"reference": "10", "mat_at_check": "10"},
            ("p1", "TEST", "Runs"): {"reference": "480", "mat_at_check": "9"},
            ("p1", "TEST", "HS"): {"reference": "122*", "explanation": "v Afghanistan"}}
    sugg = {("p1", "TEST", "Mat"): {"value": "10", "as_of": "2026-09-28"},
            ("p1", "TEST", "HS"): {"value": "122*"}}
    b = golden.merge(_blocks(), refs, sugg)[0]
    assert [r["status"] for r in b["rows"]] == ["match", "stale", "explained"]
    assert b["rows"][0]["suggestion_agrees"] and not b["rows"][2]["suggestion_agrees"]
    s = golden.summary([b])
    assert (s["match"], s["stale"], s["explained"], s["DIFF"], s["suggestion_agrees"]) == \
        (1, 1, 1, 0, 1)


def test_unexplained_difference_is_diff():
    refs = {("p1", "TEST", "HS"): {"reference": "122*"}}
    b = golden.merge(_blocks(), refs, {})[0]
    assert b["rows"][2]["status"] == "DIFF"


def test_suggestion_rows_and_csv():
    results = {"p1": {"scopes": {"TEST": {"Mat": "10", "Runs": "510"}}, "url": "u",
                      "as_of": "2026-09-28"}}
    rows = golden.suggestion_rows(results, _blocks())
    assert [(r["metric"], r["value"]) for r in rows] == [("Mat", "10"), ("Runs", "510")]
    text = golden.to_csv(golden.merge(_blocks(), {}, {}))
    assert text.splitlines()[0].split(",") == golden.CSV_COLUMNS
    assert len(text.splitlines()) == 4


def test_wiki_notes_explain_match_count_differences():
    b = {"mat": "100", "coverage_note": ""}
    assert "older than ours" in golden.wiki_note(b, "95", "2026-01-01", "2026-09-17")
    assert "newer" in golden.wiki_note(b, "104", "2026-09-28", "2026-09-17")
    assert "Afghanistan" in golden.wiki_note(b, "104", "2026-09-01", "2026-09-17")
    assert golden.wiki_note(dict(b, coverage_note="thin"), "232", "x", "y").startswith(
        "Coverage gap: Wikipedia has 132 more")
    assert golden.wiki_note(b, "100", "x", "y") == ""


def test_coverage_explanations_only_fill_unreferenced_gap_rows():
    blocks = [{"kind": "player", "id": "p1", "name": "Old Timer", "scope": "ODI", "mat": "76",
               "window": "career", "coverage_note": "thin data",
               "rows": [{"metric": "Mat", "ours": "76"}, {"metric": "Runs", "ours": "2949"},
                        {"metric": "HS", "ours": "125*"}]}]
    sugg = {("p1", "ODI", "Mat"): {"value": "232"}, ("p1", "ODI", "Runs"): {"value": "7805"},
            ("p1", "ODI", "HS"): {"value": "125*"}}
    refs = {("p1", "ODI", "Runs"): {"reference": "7805", "explanation": "already done"}}
    merged = golden.merge(blocks, refs, sugg, "2026-09-17")
    rows = golden.coverage_explanations(merged)
    assert [(r["metric"], why) for _, r, why in rows] == [
        ("Mat", golden.COVERAGE_EXPLANATION % ("76", "232"))]
    assert merged[0]["wiki_note"].startswith("Coverage gap")
