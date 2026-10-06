"""Serving-DB data-quality checks (F3 §8), evaluated BEFORE the new file is swapped in.

Pure function over measurements the build collected (serving_store.measure + transform tallies).
A non-empty failure list keeps the old database live and exits 2. Warnings are reported only.
"""
from typing import Dict, List, Tuple

# measurement → (what must hold, failure message)
_ZERO = {
    "unresolved_names": "player names with no registry entry",
    "transform_problems": "unmapped formats, dismissal kinds or outcome shapes",
    "innings_total_mismatch": "innings where total_runs != Σ runs_total + penalty runs",
    "delivery_runs_mismatch": "deliveries where runs_total != batter + extras, or extras != parts",
    "fk_violations": "foreign-key violations",
    "played_without_two_results": "matches with play that lack two team_results rows",
    "bat_runs_diff": "batting atoms' runs differ from deliveries",
    "bowl_runs_diff": "bowling atoms' runs conceded differ from deliveries",
    "bowl_balls_diff": "bowling atoms' legal balls differ from deliveries",
    "bowl_wkts_diff": "bowling atoms' wickets differ from credited dismissals",
}


def evaluate(m: Dict[str, object]) -> Tuple[List[str], List[str]]:
    """Return (failures, warnings)."""
    failures, warnings = [], []
    if m.get("quick_check") != "ok":
        failures.append("PRAGMA quick_check: %s" % m.get("quick_check"))
    if m["matches"] != m["raw_active"]:
        failures.append("serving has %d matches, raw has %d active"
                        % (m["matches"], m["raw_active"]))
    if m.get("raw_deliveries") is not None and m["deliveries"] != m["raw_deliveries"]:
        failures.append("serving has %d deliveries, raw files hold %d"
                        % (m["deliveries"], m["raw_deliveries"]))
    for key, label in _ZERO.items():
        if m.get(key):
            failures.append("%d %s" % (m[key], label))
    if m.get("played_matches") and not m.get("player_career"):
        failures.append("player_career is empty")
    if m.get("venues_unmapped"):
        warnings.append("%d venues have no country yet (sql/venue_map.csv)" % m["venues_unmapped"])
    if m.get("atoms_off_team_sheet"):
        warnings.append("%d player-innings atoms belong to players missing from the team sheet"
                        % m["atoms_off_team_sheet"])
    if m.get("players_in_both_genders"):
        ids = m["players_in_both_genders"]
        warnings.append("%d player ids appear in both men's and women's matches (Register merges;"
                        " report to Cricsheet): %s" % (len(ids), ", ".join(ids[:20])))
    return failures, warnings
