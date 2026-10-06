"""Golden-figure set (F4 §3): formatting, comparison, coverage notes, and the service keeping the
user's hand-filled columns across runs."""
import csv

import pytest

from application_logic.quality import golden
from application_logic.services import golden_service
from shared.exceptions import DataQualityError
from tests.serving.conftest import CASES, case_doc, pid

C1 = next(c for c in CASES["delivery_cases"] if c["id"].startswith("C1_"))


def test_player_rows_format_like_a_published_table():
    fig = {"matches": 3, "bat_innings": 3, "bat_not_outs": 1, "bat_runs": 120,
           "bat_high_score": 100, "bat_high_score_not_out": 1, "bat_average": 60.0,
           "bat_strike_rate": 75.4321,
           "bat_hundreds": 1, "bat_fifties": 0, "fld_catches": 2, "fld_stumpings": 0}
    rows = dict(golden.player_rows("keep", fig))
    assert rows["HS"] == "100*" and rows["Ave"] == "60.00" and "SR" not in rows
    assert rows["Mat"] == "3" and rows["St"] == "0"
    bowl = dict(golden.player_rows("bowl", {"matches": 1, "bowl_best_bowling_wkts": 5,
                                            "bowl_best_bowling_runs": 41, "bowl_average": None}))
    assert bowl["BBI"] == "5/41" and bowl["Bowl Ave"] == "-"
    assert [m for m, _ in golden.player_rows("all", fig)].count("Mat") == 1


def test_status_normalises_numbers_and_needs_an_explanation():
    assert golden.status("46.85", "", "") == ""
    assert golden.status("9230", "9,230", "") == "match"
    assert golden.status("46.85", "46.850", "") == "match"
    assert golden.status("254*", "254*", "") == "match"
    assert golden.status("94", "122*", "") == "DIFF"
    assert golden.status("94", "122*", "122* was v Afghanistan (withheld)") == "explained"
    # more matches since the check → stale (re-check); same Mat but a moved figure → regression
    assert golden.status("9300", "9230", "", mat_now="124", mat_at_check="123") == "stale"
    assert golden.status("9231", "9230", "", mat_now="123", mat_at_check="123") == "DIFF"


def test_dense_from_and_coverage_note():
    per_year = {2007: 3, 2010: 4, 2014: 30, 2015: 10, 2016: 27, 2017: 60, 2018: 31, 2019: 40,
                2020: 2, 2021: 45, 2026: 5}
    assert golden.dense_from(per_year, 2026) == 2016
    assert golden.coverage_note("2009-03-10", 2016, "women's ODI").startswith(
        "our data has far fewer women's ODI matches per year before 2016")
    assert golden.coverage_note("2017-01-01", 2016, "women's ODI") == ""
    assert golden.dense_from({}, 2026) is None


def test_service_keeps_user_columns_and_fails_on_unexplained_diff(build_env, tmp_path,
                                                                   monkeypatch):
    build_env({"1": case_doc(C1)})
    vdir = tmp_path / "validation"
    vdir.mkdir()
    (vdir / "golden-selection.csv").write_text(
        "kind,id,name,gender,scopes,role,why\n"
        "player,%s,A,male,ODI,bat,test\n"
        "team,Home|male|international,Home,male,ODI,team,\n" % pid("A"))
    serving = str(tmp_path / "db" / "cricstat.sqlite")
    monkeypatch.setattr(golden_service, "TEAM_FROM", "2000-01-01")
    s = golden_service.run(serving, str(vdir))
    assert s["status"] == "success" and s["with_reference"] == 0 and not s["missing"]
    out = vdir / "golden-figures.csv"
    rows = list(csv.DictReader(out.open()))
    runs = next(r for r in rows if r["name"] == "A" and r["metric"] == "Runs")
    assert runs["ours"] == "5"
    assert next(r for r in rows if r["name"] == "Home" and r["metric"] == "Won")["ours"] == "1"

    for r in rows:                      # the user fills two references, one of them wrong
        if r["metric"] == "Runs":
            r.update(reference="5", source="scorecard", checked_on="2026-10-06")
        if r["metric"] == "Inn":
            r.update(reference="2")
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, golden_service.COLUMNS)
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(DataQualityError) as err:
        golden_service.run(serving, str(vdir))
    assert err.value.summary["unexplained"] == 1 and err.value.summary["matches"] == 1
    kept = list(csv.DictReader(out.open()))
    assert next(r for r in kept if r["metric"] == "Runs")["source"] == "scorecard"

    for r in kept:
        if r["metric"] == "Inn":
            r["explanation"] = "test: deliberate"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, golden_service.COLUMNS)
        w.writeheader()
        w.writerows(kept)
    assert golden_service.run(serving, str(vdir))["explained"] == 1


def test_rows_go_stale_when_more_matches_are_played(build_env, tmp_path, monkeypatch):
    build_env({"1": case_doc(C1)})
    vdir = tmp_path / "validation"
    vdir.mkdir()
    (vdir / "golden-selection.csv").write_text(
        "kind,id,name,gender,scopes,role,why\nplayer,%s,A,male,ODI,bat,test\n" % pid("A"))
    serving = str(tmp_path / "db" / "cricstat.sqlite")
    golden_service.run(serving, str(vdir))
    out = vdir / "golden-figures.csv"
    rows = list(csv.DictReader(out.open()))
    for r in rows:
        if r["metric"] == "Runs":
            r["reference"] = "5"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, golden_service.COLUMNS)
        w.writeheader()
        w.writerows(rows)
    s = golden_service.run(serving, str(vdir))
    runs = next(r for r in csv.DictReader(out.open()) if r["metric"] == "Runs")
    assert s["matches"] == 1 and runs["ours_at_check"] == "5" and runs["mat_at_check"] == "1"

    build_env({"2": case_doc(C1, start_date="2026-01-05")}, mode="incremental", add=True)
    s = golden_service.run(serving, str(vdir))
    runs = next(r for r in csv.DictReader(out.open()) if r["metric"] == "Runs")
    assert s["stale"] == 1 and s["unexplained"] == 0
    assert runs["ours"] == "10" and runs["status"] == "stale"
