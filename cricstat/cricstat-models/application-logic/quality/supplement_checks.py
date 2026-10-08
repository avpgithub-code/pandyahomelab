"""Checks on the Afghanistan supplement, run on every load (forecast, selftest, CI).

Pure functions over rows already read from disk and the identifiers read from the serving DB.
Any failure means the supplement is not used: the job exits 2 and the previous forecast stays live.
SQLite can't enforce foreign keys across two files, so these checks are the integrity guarantee
(the same pattern the pipeline's build uses: count violations, refuse to swap).
"""
import collections
import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

from db_logic.repository.supplement_store import RESULT_COLUMNS

AFG = "Afghanistan"
RESULTS = {"win", "tie", "no_result"}
DECIDED_BY = {"play", "super_over", "award"}
CHECK_OK = {"confirmed", "accepted"}     # accepted = reviewed by hand; needs a note
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FIRST_ODI = "2009-04-19"                 # Afghanistan's first ODI (v Scotland, Benoni)


def check_results(rows: List[Dict[str, str]], columns: Iterable[str], known_teams: Set[str],
                  known_countries: Set[str], serving_ids: Optional[Set[str]],
                  data_as_of: Optional[str] = None,
                  restored_ids: Optional[Set[str]] = None) -> List[str]:
    """Row-level checks. `serving_ids` = every match_id in the serving DB (None in CI, where the
    DB isn't available; the NAS selftest and every forecast run pass it). `restored_ids` = serving
    matches that involve Afghanistan: Cricsheet has restored those, so the loader skips the
    supplement row (not an error). Any other collision is a wrong scorecard link (an error)."""
    restored_ids = restored_ids or set()
    errors: List[str] = []
    if tuple(columns) != RESULT_COLUMNS:
        return ["afg_odi_results.csv columns differ from %s" % (RESULT_COLUMNS,)]
    keys = collections.Counter(r["match_key"] for r in rows)
    errors += ["duplicate match_key %s" % k for k, n in keys.items() if n > 1]
    ids = collections.Counter(r["match_id"] for r in rows if r["match_id"])
    errors += ["duplicate match_id %s" % k for k, n in ids.items() if n > 1]
    for r in rows:
        key = r["match_key"] or "?"

        def bad(msg, _key=key):
            errors.append("%s: %s" % (_key, msg))

        if r["match_key"] != (r["match_id"] or "odi-%s" % r["odi_no"]):
            bad("match_key must be the match_id, or odi-<number> when there is no id")
        if not _DATE.match(r["start_date"]):
            bad("start_date %r is not YYYY-MM-DD" % r["start_date"])
        elif r["start_date"] < FIRST_ODI or (data_as_of and r["start_date"] > data_as_of):
            bad("start_date %s outside %s..%s" % (r["start_date"], FIRST_ODI, data_as_of or "-"))
        teams = (r["team1"], r["team2"])
        if (teams[0] == AFG) == (teams[1] == AFG):
            bad("Afghanistan must be on exactly one side: %s v %s" % teams)
        for t in teams:
            if t != AFG and t not in known_teams:
                bad("team %r is not a cricstat men's international team" % t)
        if r["venue_country"] not in known_countries:
            bad("venue_country %r unknown (venue_map.csv names)" % r["venue_country"])
        if r["result"] not in RESULTS:
            bad("result %r not in %s" % (r["result"], sorted(RESULTS)))
        if r["decided_by"] not in DECIDED_BY:
            bad("decided_by %r not in %s" % (r["decided_by"], sorted(DECIDED_BY)))
        if r["has_play"] not in ("0", "1"):
            bad("has_play must be 0 or 1")
        if r["result"] == "win" and r["winner"] not in teams:
            bad("winner %r is not one of the teams" % r["winner"])
        if r["result"] == "tie" and r["winner"] and r["decided_by"] != "super_over":
            bad("a tie has a winner only when a super over decided it")
        if r["result"] == "no_result" and r["winner"]:
            bad("no_result with a winner")
        if r["has_play"] == "0" and r["result"] != "no_result" and r["decided_by"] != "award":
            bad("abandoned without a ball must be no_result")
        if not r["source_page"] or not r["source_revid"]:
            bad("source_page and source_revid are required (credit + audit trail)")
        if r["check_status"] not in CHECK_OK:
            bad("second-source check is %r; review it and mark 'accepted' with a note"
                % r["check_status"])
        elif r["check_status"] == "accepted" and not r["note"]:
            bad("'accepted' needs a note saying what was checked")
        if serving_ids is not None and r["match_id"] in serving_ids and \
                r["match_id"] not in restored_ids:
            bad("match_id %s belongs to a different match in the serving DB (wrong link?)"
                % r["match_id"])
    return errors


def record_by_opponent(rows: List[Dict[str, str]]) -> Dict[str, Tuple[int, int, int, int, int]]:
    """(matches, won, lost, tied, no_result) per opponent, counting only matches where a ball was
    bowled (abandoned-without-a-ball fixtures don't count as ODIs played)."""
    rec: Dict[str, List[int]] = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
    for r in rows:
        if r["has_play"] != "1":
            continue
        opp = r["team2"] if r["team1"] == AFG else r["team1"]
        o = rec[opp]
        o[0] += 1
        if r["result"] == "win":
            o[1 if r["winner"] == AFG else 2] += 1
        elif r["result"] == "tie":
            o[3] += 1
        else:
            o[4] += 1
    return {k: tuple(v) for k, v in rec.items()}


def check_totals(rows: List[Dict[str, str]], totals: List[Dict[str, str]]) -> List[str]:
    """The supplement must reproduce the published record against every opponent, and in total."""
    ours = record_by_opponent(rows)
    errors = []
    ref = {t["opponent"]: tuple(int(t[k]) for k in ("matches", "won", "lost", "tied", "no_result"))
           for t in totals}
    total = ref.pop("TOTAL", None)
    for opp in sorted(set(ours) | set(ref)):
        a, b = ours.get(opp, (0, 0, 0, 0, 0)), ref.get(opp, (0, 0, 0, 0, 0))
        if a != b:
            errors.append("v %s: supplement %s, published %s (matches, W, L, T, NR)" % (opp, a, b))
    if total is not None:
        mine = tuple(sum(v[i] for v in ours.values()) for i in range(5))
        if mine != total:
            errors.append("total: supplement %s, published %s" % (mine, total))
    return errors
