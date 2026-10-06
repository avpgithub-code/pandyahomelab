# cricstat-pipeline

P0 data pipeline for cricstat. `full`/`recent` download Cricsheet's ball-by-ball JSON zips
and keep every match file, byte for byte, in a raw SQLite store with a run log. `register`
stores the Cricsheet Register next to them. `build` turns the raw store into the serving
database (`data/db/cricstat.sqlite`) that the API and agent read: core tables, marts,
F4 views and the semantic catalog, quality-checked before an atomic swap.

| | |
|---|---|
| Container | `cricstat-pipeline` · scheduled job, no port (image from GHCR via `cd-pull.sh`) |
| Runtime | Python standard library only · 3.8 (NAS host) and 3.12 (container) |
| Raw store | `cricstat/data/db/raw.sqlite` (journal_mode=DELETE, safe to mount read-only) |
| Serving DB | `cricstat/data/db/cricstat.sqlite` (built from raw; schema = `cricstat/sql/`) |
| Logs | `cricstat/logs/{ingest,build,register}-YYYYMMDD.log` |

## Layers (ADR-013)

| Layer | What lives there |
|---|---|
| `presentation-logic/cli/` | argparse CLI, JSON summary on stdout, exit codes (a job has no HTTP API) |
| `application-logic/services/` | `refresh_service` (download or `--zip-path`, then ingest, then prune), `ingest_service` (the one-transaction upsert), `build_service` (serving DB, full/incremental, swap), `register_service` (Register CSVs) |
| `application-logic/quality/` | `gates` (ingest) and `build_checks` (serving DB), pure functions over measured counts |
| `db-logic/loaders/` | `downloader` (urllib, retries, atomic rename, retention), `cricsheet_zip` (reads members in memory, never extracts), `register_csv` |
| `db-logic/transforms/` | `match_record` (validate a file, zlib the exact bytes) and `match_facts` (one match → serving rows, applying the F4 rules loaded from `reference_data.sql`) |
| `db-logic/repository/` + `db-logic/migrations/` | `raw_store`, `serving_store` (schema, keys, inserts, marts, checks' measurements) and versioned `NNNN_*.sql` files |
| `db-logic/marts/` | `marts.sql`: player_career / player_year / player_teams from the atoms (counts only) |
| `shared/` | env config, logging, exceptions |

The underscored names (`db_logic` etc.) are committed symlinks so Python can import the hyphenated folders.

## Usage

Run from this folder (`cricstat/cricstat-pipeline/`):

```sh
python3 -m presentation_logic.cli full      # monthly: all_json.zip (~147 MB), detects removed matches
python3 -m presentation_logic.cli recent    # daily: recently_added_7_json.zip, upsert only
python3 -m presentation_logic.cli full --zip-path ../data/raw/all_json-20261005.zip   # no network
python3 -m presentation_logic.cli recent --quiet   # only warnings on stderr (Task Scheduler)
python3 -m presentation_logic.cli register         # weekly: people.csv + names.csv → raw store
python3 -m presentation_logic.cli build            # after every ingest: incremental serving DB
python3 -m presentation_logic.cli build --full     # monthly / after a rule change: from scratch
```

What a run does, in one SQLite transaction:

1. Downloads to `data/raw/<name>.zip.part`, checks it is a complete zip, renames it to
   `data/raw/<name>-YYYYMMDD.zip`. The last 3 full zips (7 recent zips) are kept.
2. Reads every `*.json` member straight from the zip; anything else (`README.txt`) is skipped.
3. Upserts by `match_id` with a sha256 of the file bytes: new id → **added**, different hash →
   **updated**, same hash → **unchanged** (only `last_seen_at` moves). Unchanged files are not re-parsed.
4. `full` only: active ids missing from the zip get `removed_at` set (rows are never deleted).
   An id that comes back, in either mode, has `removed_at` cleared (**restored**).
5. Runs the data-quality gates, then COMMITs. Any failure rolls the whole run back; the
   `ingest_runs` row is then marked `dq_failed` or `error` in a separate small transaction.

Re-running the same zip gives 0 added / 0 updated.

### Data-quality gates

| Gate | Fails the run when |
|---|---|
| Parse | files that aren't valid JSON with `info` and `innings` > max(5, 0.5% of files) |
| Active drop (`full`) | active matches would fall more than 2% below the count before the run |
| Empty (`full`) | the zip has no match files |
| match_id | not a gate: non-digit ids are stored, counted (`nondigit_ids`) and listed in `notes` |

### Serving-DB build

`build` writes `data/db/cricstat.sqlite.new`, checks it, records the build in `build_info`, then
`os.replace`s it over the live file (readers reopen when `build_info` changes).

| Mode | What it does |
|---|---|
| `--full` | Every active raw match → core tables (bulk load, indexes after) → marts → views → catalog |
| `--incremental` (default) | Copies the live DB, re-inserts only matches whose raw sha256 changed or that were removed, recomputes marts, players, venues, views, catalog. Becomes `full` when there is no live DB or `rules_sha` changed (schema, `reference_data.sql`, transform code). Does nothing, and keeps the live file, when nothing changed |

The cricket rules are data (`cricstat/sql/reference_data.sql`); ratios exist only in
`semantic_views.sql`; `semantic_catalog.sql` describes them; `venue_map.csv` (hand-checked)
gives venues a country for home/away. Players are everyone named in a match registry; the
Register supplies their full names, cross-site ids (`key_cricinfo`, `_2`, `_3` → `cricinfo`)
and name variants.

Checks before the swap (any failure → exit 2, live DB kept, rejected file kept as
`cricstat.sqlite.failed`): `quick_check`; matches = raw active matches; deliveries = deliveries in
the raw files (full); innings totals = Σ runs + penalties; every delivery's runs add up; no
unresolved player names; no unmapped format / dismissal kind / outcome; no FK violations; two
`team_results` per match with play; atoms agree with deliveries (runs, runs conceded, legal
balls, credited wickets). Warnings only: unmapped venues, atoms for players missing from the team
sheet.

Run it **after** the ingest, never alongside: SQLite in DELETE-journal mode lets a long reader
(the build reads raw for minutes) block the ingest's write.

## Output and exit codes

stdout is one JSON line, e.g.

```json
{"mode": "full", "status": "success", "added": 0, "updated": 0, "unchanged": 22983, "failed": 0,
 "removed": 0, "restored": 0, "skipped": 1, "active_before": 22983, "active_after": 22983,
 "duration_s": 56.6, "total_duration_s": 57.5, "run_id": 2, "exit_code": 0, ...}
```

`duration_s` covers the ingest transaction; `total_duration_s` includes the download.

| Exit | Meaning |
|---|---|
| 0 | success (committed) |
| 1 | runtime error: download, missing/corrupt zip, SQLite error (rolled back) |
| 2 | a data-quality gate failed (rolled back; for `build`, the live DB is kept) |

## Environment

Relative paths resolve against `CRICSTAT_HOME` (default: the `cricstat/` folder; `/cricstat` in the image).
See `.env.example`.

| Variable | Default |
|---|---|
| `CRICSTAT_HOME` | parent of `cricstat-pipeline/` |
| `CRICSTAT_DATA_DIR` | `data` |
| `CRICSTAT_RAW_ZIP_DIR` | `data/raw` |
| `CRICSTAT_RAW_DB` | `data/db/raw.sqlite` |
| `CRICSTAT_SERVING_DB` | `data/db/cricstat.sqlite` |
| `CRICSTAT_SQL_DIR` / `CRICSTAT_VENUE_MAP` | `sql` / `sql/venue_map.csv` |
| `CRICSTAT_PEOPLE_URL` / `CRICSTAT_NAMES_URL` | `https://cricsheet.org/register/people.csv` / `names.csv` |
| `CRICSTAT_KEEP_REGISTER_CSVS` | `4` |
| `CRICSTAT_MAX_REGISTER_DROP_FRAC` | `0.02` |
| `CRICSTAT_LOG_DIR` | `logs` |
| `CRICSTAT_LOG_LEVEL` | `INFO` |
| `CRICSTAT_FULL_URL` | `https://cricsheet.org/downloads/all_json.zip` |
| `CRICSTAT_RECENT_URL` | `https://cricsheet.org/downloads/recently_added_7_json.zip` |
| `CRICSTAT_USER_AGENT` | `cricstat/0.1 (+https://pandyahomelab.com/cricket/)` |
| `CRICSTAT_HTTP_TIMEOUT` / `_RETRIES` / `_BACKOFF` | `60` s / `4` / `5` s (doubles each retry) |
| `CRICSTAT_KEEP_FULL_ZIPS` / `_RECENT_ZIPS` | `3` / `7` |
| `CRICSTAT_MAX_FAILED_ABS` / `_FRAC` | `5` / `0.005` |
| `CRICSTAT_MAX_ACTIVE_DROP_FRAC` | `0.02` |

## Schema

`db-logic/migrations/0001_init.sql`; applied versions are in `schema_version`.

- `matches_raw`: `match_id` PK, `sha256`, `json_zlib` (zlib of the exact file bytes),
  `json_bytes`, `data_version`, `revision`, `match_type`, `gender`, `team_type`,
  `start_date` (earliest of `info.dates`), `teams` (JSON array), `event_name`,
  `first_seen_at`, `last_seen_at`, `updated_at`, `removed_at`, `last_run_id`.
  Indexed on `start_date`, `match_type`, `gender`.
- `ingest_runs`: one row per run with mode, source, source zip sha256, status
  (`running`/`success`/`dq_failed`/`error`), counts, active before/after, and `notes` (JSON).

Read a match back: `json.loads(zlib.decompress(row["json_zlib"]))`.

## Develop

```sh
python3 -m pip install --user -r requirements-dev.txt
python3 -m ruff check .
python3 -m pytest -q          # tiny synthetic zips in tmp dirs; no network
```

The Dockerfile (`docker/Dockerfile`, python:3.12-slim, non-root) builds from context `cricstat/`
so `cricstat/sql/` is copied to `/cricstat/sql`. CI builds and publishes it; the NAS never builds it.
It expects `cricstat/data` and `cricstat/logs` mounted at `/cricstat/data` and `/cricstat/logs`.

## Data notes (first load, 2026-10-05)

- 22,983 matches, 2001-12-19 to 2026-09-17, all `data_version` 1.2.0; 0 parse failures.
- 25 match ids are not digits: `wi_*`, West Indies women's domestic matches (T20 Blaze,
  Women's Super50, 2019 and 2022). So match_id is *not* always an ESPNcricinfo id.
- About 4.0 GB of JSON compresses to 145 MB in `json_zlib`; the database is ~168 MB.

## Attribution

Match data from Cricsheet (cricsheet.org), used under the Open Data Commons Attribution License 1.0.
