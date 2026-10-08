"""The reviewed files that ship in the image: supplement + crosswalks + tournament configs.
These run in CI without the serving DB (the NAS selftest repeats them against the real DB)."""
import os

from application_logic.quality import supplement_checks as checks
from application_logic.services import tournament_service
from db_logic.repository import supplement_store as store
from db_logic.repository import tournament_store
from tests.conftest import CRICSTAT, ROOT

SUPP = os.path.join(ROOT, "supplement")
TOURN = os.path.join(ROOT, "tournaments")
VENUE_MAP = os.path.join(CRICSTAT, "sql", "venue_map.csv")


def _known():
    teams = set(store.team_codes(SUPP).values()) - {"Afghanistan"}
    import csv
    with open(VENUE_MAP, encoding="utf-8") as f:
        countries = {r["country"] for r in csv.DictReader(f) if r["country"]}
    return teams, countries


def test_supplement_structure_and_checksum():
    rows = store.read_results(SUPP)
    teams, countries = _known()
    errs = [e for e in checks.check_results(rows, store.header(os.path.join(SUPP, store.RESULTS_FILE)),
                                            teams, countries, None)
            if "second-source check" not in e and "needs a note" not in e]
    assert errs == []
    assert checks.check_totals(rows, store.read_totals(SUPP)) == []
    assert min(r["start_date"] for r in rows) == checks.FIRST_ODI


def test_supplement_review_is_complete():
    """Gate: every row is confirmed by a second source or accepted by a reviewer with a note."""
    pending = ["%s %s %s v %s (%s)" % (r["match_key"], r["start_date"], r["team1"], r["team2"],
                                       r["check_status"])
               for r in store.read_results(SUPP)
               if r["check_status"] not in checks.CHECK_OK
               or (r["check_status"] == "accepted" and not r["note"])]
    assert pending == [], "%d rows await review:\n%s" % (len(pending), "\n".join(pending))


def test_crosswalk_targets_are_unique_per_token():
    codes = store.team_codes(SUPP)
    assert codes["AFG"] == codes["Afghanistan"] == "Afghanistan"
    assert codes["USA"] == "United States of America" and codes["UAE"] == "United Arab Emirates"


def test_committed_tournaments_validate():
    teams, _ = _known()
    seen = []
    for tid in tournament_store.tournament_ids(TOURN):
        fmt = tournament_store.read_format(TOURN, tid)
        if fmt.get("status") == "field_tbc":
            continue
        fixtures = tournament_store.read_fixtures(TOURN, tid)
        assert tournament_service.validate(fmt, fixtures, teams | {"Afghanistan"}) == [], tid
        seen.append((tid, len(fixtures)))
    assert seen == [("wc2019", 48), ("wc2023", 48), ("wc2027", 57)]


def test_past_world_cups_record_what_happened():
    for tid, champion, standings_top4 in (
            ("wc2019", "England", ["India", "Australia", "England", "New Zealand"]),
            ("wc2023", "Australia", ["India", "South Africa", "Australia", "New Zealand"])):
        fmt = tournament_store.read_format(TOURN, tid)
        fixtures = tournament_store.read_fixtures(TOURN, tid)
        assert fmt["final_standings"]["L"][:4] == standings_top4
        final = [f for f in fixtures if f["stage"] == "final"][0]
        assert final["winner"] == champion
        assert all(f["result"] for f in fixtures)                 # every result recorded
        afg = [f for f in fixtures if "Afghanistan" in (f["team1"], f["team2"])]
        assert len(afg) == 9                                      # restored from the supplement


def test_2027_assumptions_are_listed():
    fmt = tournament_store.read_format(TOURN, "wc2027")
    tbc = [a for a in fmt["assumptions"] if a.startswith("TBC")]
    assert len(tbc) >= 4                      # each unpublished rule is named, not hidden
    assert fmt["stages"][1]["groups"]["A"][:2] == ["India", "Australia"]
