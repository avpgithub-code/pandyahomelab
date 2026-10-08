"""The rating input: official men's ODIs from the serving DB plus the reviewed Afghanistan
supplement.

One row per match, oldest first, keyed by stable identifiers only:
    match_key (ESPNcricinfo id, or odi-<number>), start_date, team1, team2 (cricstat team names),
    venue_country, home (the team playing in its own country, or None), result, winner, method,
    decided_by, has_play, source ('cricsheet' | 'supplement:wikipedia'), event
Home/away follows the build's rule (serving_store.apply_venue_map): a team is at home when the
venue's country equals its name. The same rule applies to supplement rows, so Afghanistan, which has
never hosted an ODI at home, is never 'home'.
Every check must pass, otherwise DataCheckError (exit 2) and nothing downstream runs.
"""
import collections
import csv
from typing import Dict, List, Optional, Tuple

from application_logic.quality import supplement_checks as checks
from db_logic.repository import serving_reader
from db_logic.repository import supplement_store as store
from shared.exceptions import DataCheckError

SUPPLEMENT_SOURCE = "supplement:wikipedia"


def known_countries(venue_map_path: str) -> set:
    with open(venue_map_path, encoding="utf-8", newline="") as f:
        return {r["country"].strip() for r in csv.DictReader(f) if r.get("country")}


def _home(team1: str, team2: str, country: Optional[str]) -> Optional[str]:
    if country == team1:
        return team1
    if country == team2:
        return team2
    return None


def load_supplement(cfg, serving_ids: Optional[set], known_teams: set, data_as_of: Optional[str],
                    restored: Optional[List[Dict[str, str]]] = None
                    ) -> Tuple[List[Dict[str, str]], List[str], List[str]]:
    """Read + check the supplement. Returns (rows to use, errors, restored match keys).
    `restored` = Afghanistan matches Cricsheet now publishes (supplement-shaped rows): those win,
    the supplement's copy is skipped, and the checksum counts both sources together."""
    d = cfg.SUPPLEMENT_DIR
    rows = store.read_results(d)
    restored = restored or []
    restored_ids = {r["match_id"] for r in restored}
    errors = checks.check_results(rows, store.header("%s/%s" % (d, store.RESULTS_FILE)),
                                  known_teams, known_countries(cfg.VENUE_MAP), serving_ids,
                                  data_as_of, restored_ids)
    use = [r for r in rows if r["match_id"] not in restored_ids]
    errors += checks.check_totals(use + restored, store.read_totals(d))
    skipped = sorted(r["match_key"] for r in rows if r["match_id"] in restored_ids)
    return use, errors, skipped


def load_matches(cfg, conn=None) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    """All rated men's ODIs (both sources) + a report. Raises DataCheckError on any failed check."""
    own = conn is None
    conn = conn or serving_reader.connect(cfg.SERVING_DB)
    try:
        info = serving_reader.build_info(conn)
        data_as_of = info.get("data_as_of")
        serving = serving_reader.men_odi_results(conn)
        serving_ids = serving_reader.all_match_ids(conn)
        teams = serving_reader.men_international_teams(conn)
    finally:
        if own:
            conn.close()
    restored = [{"match_id": r["match_id"], "team1": r["team1"], "team2": r["team2"],
                 "result": r["result"], "winner": r["winner"] or "", "has_play": "1"}
                for r in serving if checks.AFG in (r["team1"], r["team2"])]
    supp, errors, skipped = load_supplement(cfg, serving_ids, teams, data_as_of, restored)
    if errors:
        raise DataCheckError("Afghanistan supplement failed %d check(s): %s"
                             % (len(errors), "; ".join(errors[:10])))
    rows: List[Dict[str, object]] = []
    for r in serving:
        rows.append({
            "match_key": r["match_id"], "start_date": r["start_date"], "team1": r["team1"],
            "team2": r["team2"], "venue_country": r["venue_country"],
            "home": _home(r["team1"], r["team2"], r["venue_country"]), "result": r["result"],
            "winner": r["winner"], "method": r["method"], "decided_by": r["decided_by"],
            "has_play": 1, "source": "cricsheet", "event": r["event"]})
    for r in supp:
        rows.append({
            "match_key": r["match_key"], "start_date": r["start_date"], "team1": r["team1"],
            "team2": r["team2"], "venue_country": r["venue_country"],
            "home": _home(r["team1"], r["team2"], r["venue_country"]), "result": r["result"],
            "winner": r["winner"] or None, "method": r["method"] or None,
            "decided_by": r["decided_by"], "has_play": int(r["has_play"]),
            "source": SUPPLEMENT_SOURCE, "event": None})
    rows.sort(key=lambda r: (r["start_date"], str(r["match_key"])))
    problems = check_combined(rows)
    if problems:
        raise DataCheckError("rating input failed %d check(s): %s"
                             % (len(problems), "; ".join(problems[:10])))
    by_source = collections.Counter(r["source"] for r in rows)
    return rows, {
        "matches": len(rows), "by_source": dict(by_source),
        "first": rows[0]["start_date"] if rows else None,
        "last": rows[-1]["start_date"] if rows else None,
        "data_as_of": data_as_of, "build_id": info.get("build_id"),
        "teams": len({t for r in rows for t in (r["team1"], r["team2"])}),
        "restored_by_cricsheet": skipped,
    }


def check_combined(rows: List[Dict[str, object]]) -> List[str]:
    problems = []
    keys = collections.Counter(r["match_key"] for r in rows)
    problems += ["match_key %s appears %d times" % (k, n) for k, n in keys.items() if n > 1]
    for r in rows:
        if r["team1"] == r["team2"]:
            problems.append("%s: a team plays itself" % r["match_key"])
        if {r["team1"], r["team2"]} & serving_reader.COMPOSITE_SIDES:
            problems.append("%s: composite side in the rating input" % r["match_key"])
    return problems
