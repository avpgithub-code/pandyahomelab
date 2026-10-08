"""The reviewed Afghanistan results supplement: CSV files shipped inside the models image.

    supplement/afg_odi_results.csv   one row per Afghanistan men's ODI (incl. abandoned ones)
    supplement/afg_totals.csv        the checksum: record per opponent from the team article
    supplement/team_codes.csv        crosswalk: Wikipedia team code/name → cricstat team name
    supplement/supplement_venues.csv crosswalk: city → venue country, where venue_map.csv has no
                                     unambiguous answer
    supplement/reviews.csv           reviewer decisions: accept a row, or correct one field

Rows are keyed by `match_key` = the ESPNcricinfo match_id (Cricsheet's own id space), or
"odi-<number>" when the source has no scorecard link. Plain CSV, so every change is a reviewable
diff.
"""
import csv
import os
from typing import Dict, List

RESULTS_FILE = "afg_odi_results.csv"
TOTALS_FILE = "afg_totals.csv"
TEAM_CODES_FILE = "team_codes.csv"
VENUES_FILE = "supplement_venues.csv"
REVIEWS_FILE = "reviews.csv"

RESULT_COLUMNS = (
    "match_key", "match_id", "odi_no", "start_date", "team1", "team2", "venue", "city",
    "venue_country", "result", "winner", "method", "decided_by", "has_play", "margin",
    "source_page", "source_revid", "check_article", "check_status", "note",
)
TOTALS_COLUMNS = ("opponent", "matches", "won", "lost", "tied", "no_result", "source_page",
                  "source_revid", "as_of")


def _read(path: str) -> List[Dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def _write(path: str, columns, rows: List[Dict[str, object]]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(columns), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: "" if r.get(k) is None else r.get(k) for k in columns})
    os.replace(tmp, path)


def header(path: str) -> List[str]:
    with open(path, encoding="utf-8", newline="") as f:
        return next(csv.reader(f), [])


def read_results(directory: str) -> List[Dict[str, str]]:
    return _read(os.path.join(directory, RESULTS_FILE))


def write_results(directory: str, rows: List[Dict[str, object]]) -> None:
    rows = sorted(rows, key=lambda r: (r["start_date"], str(r["match_key"])))
    _write(os.path.join(directory, RESULTS_FILE), RESULT_COLUMNS, rows)


def read_totals(directory: str) -> List[Dict[str, str]]:
    return _read(os.path.join(directory, TOTALS_FILE))


def write_totals(directory: str, rows: List[Dict[str, object]]) -> None:
    _write(os.path.join(directory, TOTALS_FILE), TOTALS_COLUMNS, rows)


def team_codes(directory: str) -> Dict[str, str]:
    """Token (code or name as Wikipedia writes it) → cricstat team name."""
    return {r["token"]: r["team_name"] for r in _read(os.path.join(directory, TEAM_CODES_FILE))}


def read_reviews(directory: str) -> List[Dict[str, str]]:
    path = os.path.join(directory, REVIEWS_FILE)
    return _read(path) if os.path.exists(path) else []


def venue_overrides(directory: str) -> Dict[str, str]:
    """City → country, for cities venue_map.csv doesn't settle."""
    path = os.path.join(directory, VENUES_FILE)
    if not os.path.exists(path):
        return {}
    return {r["city"]: r["country"] for r in _read(path)}
