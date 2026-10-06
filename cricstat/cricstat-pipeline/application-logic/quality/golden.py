"""Golden-figure comparison (F4 §3): our figures vs reference figures read by hand from public
records. Pure functions; no SQL, no I/O.

A row is a match when the strings agree after normalising numbers (ratios to 2 decimals, as
published). A difference is acceptable only with a written explanation; any unexplained difference
fails the check (exit 2).
"""
import statistics
from typing import Dict, List, Optional

BATTING = [("Mat", "matches"), ("Inn", "bat_innings"), ("NO", "bat_not_outs"),
           ("Runs", "bat_runs"), ("HS", None), ("Ave", "bat_average"), ("100", "bat_hundreds")]
BOWLING = [("Mat", "matches"), ("Bowl Inn", "bowl_innings"), ("Wkts", "bowl_wickets"),
           ("BBI", None), ("Bowl Ave", "bowl_average"), ("Econ", "bowl_economy"),
           ("5w", "bowl_five_wkt_hauls")]
KEEPING = [("Ct", "fld_catches"), ("St", "fld_stumpings")]
TEAM = [("Mat", "matches"), ("Won", "won"), ("Lost", "lost"), ("Tied", "tied"),
        ("Drawn", "drawn"), ("NR", "no_result"), ("Win %", "win_pct")]
ROLE_SECTIONS = {"bat": (BATTING,), "keep": (BATTING, KEEPING), "bowl": (BOWLING,),
                 "all": (BATTING, BOWLING)}
RATIOS = {"Ave", "Bowl Ave", "Econ", "Win %"}


def fmt(metric: str, value) -> str:
    """Render like a published scorecard table: ratios to 2 dp, '-' when undefined."""
    if value is None:
        return "-"
    if metric in RATIOS:
        return "%.2f" % value
    return str(value)


def player_rows(role: str, fig: Dict[str, object]) -> List[tuple]:
    """[(metric, ours)] for one player-scope, in published-table order. Mat is shown once."""
    rows, seen = [], set()
    for section in ROLE_SECTIONS[role]:
        for metric, key in section:
            if metric in seen:
                continue
            seen.add(metric)
            if metric == "HS":
                hs = fig.get("bat_high_score")
                value = "-" if hs is None else "%d%s" % (
                    hs, "*" if fig.get("bat_high_score_not_out") else "")
            elif metric == "BBI":
                w, r = fig.get("bowl_best_bowling_wkts"), fig.get("bowl_best_bowling_runs")
                value = "-" if w is None else "%d/%d" % (w, r)
            else:
                value = fmt(metric, fig.get(key))
            rows.append((metric, value))
    return rows


def team_rows(rec: Dict[str, object]) -> List[tuple]:
    rows = []
    for metric, key in TEAM:
        value = rec.get(key)
        rows.append((metric, fmt(metric, 0 if value is None and key != "win_pct" else value)))
    return rows


def _norm(text: str) -> str:
    text = (text or "").strip().replace(",", "")
    try:
        return "%.2f" % float(text)
    except ValueError:
        return text.replace(" ", "")


def status(ours: str, reference: str, explanation: str, mat_now: str = "",
           mat_at_check: str = "") -> Optional[str]:
    """'' when no reference yet; 'stale' when the player or team has played more matches since
    the reference was entered (re-check; does not fail); else 'match', 'explained', or 'DIFF'
    (fails the check). A figure that moves while Mat stays the same is a regression → DIFF."""
    if not (reference or "").strip():
        return ""
    if mat_at_check and mat_now != mat_at_check:
        return "stale"
    if _norm(ours) == _norm(reference):
        return "match"
    return "explained" if (explanation or "").strip() else "DIFF"


def dense_from(per_year: Dict[int, int], current_year: int) -> Optional[int]:
    """First year after which every full year has at least half the median match count.
    2020 (COVID) and the current, partial year are ignored. None when there is no data."""
    years = sorted(y for y in per_year if y not in (2020, current_year))
    if not years:
        return None
    floor = statistics.median(per_year[y] for y in years) / 2
    start = years[-1]
    for y in reversed(years):
        if per_year[y] < floor:
            break
        start = y
    return start


def coverage_note(first_date: Optional[str], dense_year: Optional[int], label: str) -> str:
    """Flag careers that begin before the data is dense for this format."""
    if not first_date or dense_year is None or int(first_date[:4]) >= dense_year:
        return ""
    return ("our data has far fewer %s matches per year before %d, and this career starts %s in"
            " it: it may be incomplete (compare Mat first)" % (label, dense_year, first_date))
