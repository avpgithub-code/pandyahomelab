"""Supplement checks, the combined rating input and tournament validation (P1.1)."""
import pytest

from application_logic.quality import supplement_checks as checks
from application_logic.services import data_service, tournament_service
from db_logic.repository import supplement_store as store
from shared.exceptions import DataCheckError
from tests.conftest import make_serving_db, supp_row, totals_for

KNOWN = {"India", "Australia", "Ireland", "Scotland", "Pakistan"}
COUNTRIES = {"India", "Australia", "Ireland", "United Arab Emirates", "Pakistan", "Scotland"}
COLS = store.RESULT_COLUMNS


def errors_for(**kw):
    return checks.check_results([supp_row(**kw)], COLS, KNOWN, COUNTRIES, set(), "2026-10-07")


def test_valid_row_passes():
    assert errors_for() == []


@pytest.mark.parametrize("kw, fragment", [
    ({"team1": "Ireland"}, "exactly one side"),
    ({"team2": "Afghanistan"}, "exactly one side"),
    ({"team2": "Narnia"}, "not a cricstat"),
    ({"venue_country": "Atlantis"}, "venue_country"),
    ({"result": "draw"}, "result"),
    ({"winner": "India"}, "not one of the teams"),
    ({"result": "no_result"}, "no_result with a winner"),
    ({"has_play": "0"}, "abandoned without a ball"),
    ({"start_date": "2008-12-31"}, "outside"),
    ({"start_date": "2026-12-01"}, "outside"),
    ({"source_revid": ""}, "source_page and source_revid"),
    ({"check_status": "not_found"}, "second-source check"),
    ({"check_status": "accepted"}, "needs a note"),
    ({"match_key": "odi-4000"}, "match_key must be"),
])
def test_each_rule(kw, fragment):
    assert any(fragment in e for e in errors_for(**kw)), errors_for(**kw)


def test_duplicates_and_columns():
    rows = [supp_row(), supp_row()]
    errs = checks.check_results(rows, COLS, KNOWN, COUNTRIES, None)
    assert any("duplicate match_key" in e for e in errs)
    assert checks.check_results([supp_row()], COLS[:-1], KNOWN, COUNTRIES, None)


def test_wrong_link_is_an_error_but_a_restored_match_is_not():
    row = [supp_row(match_id="555")]
    assert any("wrong link" in e for e in
               checks.check_results(row, COLS, KNOWN, COUNTRIES, {"555"}))
    assert checks.check_results(row, COLS, KNOWN, COUNTRIES, {"555"}, restored_ids={"555"}) == []


def test_totals_count_only_matches_with_play():
    rows = [supp_row(), supp_row(match_id="900002", odi_no="4001a", result="no_result", winner="",
                                 has_play="0"),
            supp_row(match_id="900003", odi_no="4002", team1="India", team2="Afghanistan",
                     winner="India")]
    assert checks.record_by_opponent(rows) == {"Ireland": (1, 1, 0, 0, 0), "India": (1, 0, 1, 0, 0)}
    assert checks.check_totals(rows, totals_for(rows)) == []
    wrong = totals_for(rows)
    wrong[-1]["lost"] = "2"
    assert checks.check_totals(rows, wrong) == ["total: supplement (2, 1, 1, 0, 0), "
                                                "published (2, 1, 2, 0, 0)"]


def _write_supplement(cfg, rows):
    store.write_results(cfg.SUPPLEMENT_DIR, rows)
    store.write_totals(cfg.SUPPLEMENT_DIR, totals_for(rows))


SERVING = [
    ("100", "2018-01-10", "India", "Australia", "India", "win", "India"),
    ("101", "2018-01-12", "Australia", "India", "India", "no_result", None),
    ("102", "2018-02-01", "Asia XI", "Africa XI", "India", "win", "Asia XI"),     # composite
    ("103", "2018-02-05", "Ireland", "Scotland", "Scotland", "win", "Scotland"),
    ("104", "2018-02-06", "Ireland", "Scotland", "Scotland", "win", "Ireland", "ODM"),  # not ODI
]


def test_combined_input_merges_sources_and_applies_one_home_rule(cfg):
    make_serving_db(cfg.SERVING_DB, SERVING)
    _write_supplement(cfg, [supp_row(start_date="2018-01-11")])
    rows, rep = data_service.load_matches(cfg)
    assert [r["match_key"] for r in rows] == ["100", "900001", "101", "103"]
    assert rep["by_source"] == {"cricsheet": 3, "supplement:wikipedia": 1}
    by = {r["match_key"]: r for r in rows}
    assert by["100"]["home"] == "India" and by["103"]["home"] == "Scotland"
    assert by["900001"]["home"] is None                 # Afghanistan in the UAE: neutral
    assert rep["restored_by_cricsheet"] == []


def test_unreviewed_supplement_blocks_everything(cfg):
    make_serving_db(cfg.SERVING_DB, SERVING)
    _write_supplement(cfg, [supp_row(check_status="not_found")])
    with pytest.raises(DataCheckError, match="second-source check"):
        data_service.load_matches(cfg)


def test_restored_cricsheet_match_wins_and_supplement_copy_is_skipped(cfg):
    restored = ("900001", "2018-03-01", "Afghanistan", "Ireland", "United Arab Emirates", "win",
                "Afghanistan")
    make_serving_db(cfg.SERVING_DB, SERVING + [restored])
    _write_supplement(cfg, [supp_row()])
    rows, rep = data_service.load_matches(cfg)
    assert rep["restored_by_cricsheet"] == ["900001"]
    assert [r["source"] for r in rows if r["match_key"] == "900001"] == ["cricsheet"]


def test_withdrawing_the_supplement_leaves_cricsheet_only(cfg):
    make_serving_db(cfg.SERVING_DB, SERVING)
    _write_supplement(cfg, [])
    rows, rep = data_service.load_matches(cfg)
    assert rep["by_source"] == {"cricsheet": 3}


FMT = {"id": "t", "teams": ["India", "Australia", "Pakistan"],
       "stages": [{"id": "league", "kind": "round_robin", "groups": {"L": ["India", "Australia",
                                                                            "Pakistan"]}}]}


def _fx(no, s1, s2, stage="league", group="L"):
    return {"match_no": str(no), "stage": stage, "group": group, "date": "2027-10-0%d" % no,
            "slot1": s1, "slot2": s2, "venue": "V", "city": "C", "venue_country": "India"}


def test_tournament_round_robin_must_be_complete_and_slots_known():
    good = [_fx(1, "India", "Australia"), _fx(2, "India", "Pakistan"),
            _fx(3, "Australia", "Pakistan"), _fx(4, "L1", "L2", "final", "")]
    assert tournament_service.validate(FMT, good, KNOWN) == []
    missing = good[:2] + good[3:]
    assert any("single round robin" in e for e in tournament_service.validate(FMT, missing, KNOWN))
    bad_slot = good[:3] + [_fx(4, "L1", "Winner of the other one", "final", "")]
    assert any("neither a team nor a placeholder" in e
               for e in tournament_service.validate(FMT, bad_slot, KNOWN))
    no_country = [dict(good[0], venue_country="")] + good[1:]
    assert any("no venue country" in e for e in tournament_service.validate(FMT, no_country, KNOWN))
