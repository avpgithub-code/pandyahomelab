"""Fetch the pre-aggregated NYC CitiBike daily ride counts CSV.

Source: toddwschneider/nyc-citibike-data
URL: https://raw.githubusercontent.com/toddwschneider/nyc-citibike-data/
     master/data/daily_citi_bike_trip_counts_and_weather.csv

This script runs ONCE locally (or in CI) to produce
db-logic/data/bike_share_daily.csv, which is then committed to the repo.
The Docker image bakes the committed CSV at build time, so containers
never fetch at runtime — v1.0.0 has fixed, reproducible training data.

Idempotent: skips if the target CSV exists and validates OK. Pass --force
to refetch unconditionally.

Usage:
    python db-logic/scripts/build_dataset.py
    python db-logic/scripts/build_dataset.py --force
"""
import argparse
import csv
import hashlib
import os
import sys
import urllib.request
from datetime import datetime

SOURCE_URL = (
    "https://raw.githubusercontent.com/toddwschneider/nyc-citibike-data/"
    "master/data/daily_citi_bike_trip_counts_and_weather.csv"
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "db-logic", "data", "bike_share_daily.csv")

REQUIRED_COLUMNS = {"date", "trips"}
MIN_ROWS = 500
EXPECTED_FIRST_DATE_PREFIX = "2013"
EXPECTED_LAST_DATE_PREFIX_RANGE = ("2014", "2030")  # last row should be ≥ 2014


def fetch(url: str) -> bytes:
    print(f"[build_dataset] fetching {url}", flush=True)
    with urllib.request.urlopen(url, timeout=60) as resp:
        if resp.status != 200:
            raise RuntimeError(f"unexpected HTTP status {resp.status} from source")
        return resp.read()


def validate(csv_bytes: bytes) -> dict:
    text = csv_bytes.decode("utf-8")
    reader = csv.DictReader(text.splitlines())
    cols = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - cols
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}. Found: {sorted(cols)}")
    rows = list(reader)
    if len(rows) < MIN_ROWS:
        raise ValueError(f"CSV has only {len(rows)} rows; expected ≥ {MIN_ROWS}")
    first_date = rows[0]["date"].strip('"')
    last_date = rows[-1]["date"].strip('"')
    if not first_date.startswith(EXPECTED_FIRST_DATE_PREFIX):
        raise ValueError(f"first row date {first_date!r} does not start with {EXPECTED_FIRST_DATE_PREFIX!r}")
    lo, hi = EXPECTED_LAST_DATE_PREFIX_RANGE
    last_year = last_date[:4]
    if not (lo <= last_year <= hi):
        raise ValueError(f"last row date {last_date!r} not in expected year range [{lo}, {hi}]")
    # trips must be a positive integer in every row
    for i, r in enumerate(rows):
        try:
            t = int(r["trips"])
        except (KeyError, ValueError) as e:
            raise ValueError(f"row {i}: trips column is not an integer: {r.get('trips')!r}") from e
        if t < 0:
            raise ValueError(f"row {i}: negative trips count {t}")
    return {
        "rows": len(rows),
        "first_date": first_date,
        "last_date": last_date,
        "sha256": hashlib.sha256(csv_bytes).hexdigest()[:16],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--force", action="store_true", help="refetch even if output exists")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    if os.path.exists(OUTPUT_PATH) and not args.force:
        with open(OUTPUT_PATH, "rb") as f:
            existing = f.read()
        try:
            stats = validate(existing)
            print(
                f"[build_dataset] OK existing CSV: {stats['rows']} rows "
                f"({stats['first_date']} → {stats['last_date']}, sha256[:16]={stats['sha256']}). "
                f"Use --force to refetch.",
                flush=True,
            )
            return 0
        except ValueError as e:
            print(f"[build_dataset] existing CSV failed validation: {e}. Refetching.", flush=True)

    csv_bytes = fetch(SOURCE_URL)
    stats = validate(csv_bytes)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(csv_bytes)
    print(
        f"[build_dataset] wrote {OUTPUT_PATH} — {stats['rows']} rows "
        f"({stats['first_date']} → {stats['last_date']}, sha256[:16]={stats['sha256']}, "
        f"{len(csv_bytes)} bytes). Generated at {datetime.utcnow().isoformat()}Z.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
