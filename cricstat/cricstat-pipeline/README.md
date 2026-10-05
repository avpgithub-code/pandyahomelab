# cricstat-pipeline

P0 ingestion for cricstat: downloads Cricsheet's ball-by-ball JSON zips and keeps every
match file, byte for byte, in a raw SQLite store with a run log. Later stages (core
tables, marts, models) read from this store and never from the zips.

| | |
|---|---|
| Container | `cricstat-pipeline` · scheduled job, no port (image not built yet) |
| Runtime | Python standard library only · 3.8 (NAS host) and 3.12 (container) |
| Raw store | `cricstat/data/db/raw.sqlite` (journal_mode=DELETE, safe to mount read-only) |
| Logs | `cricstat/logs/ingest-YYYYMMDD.log` |

## Layers (ADR-013)

| Layer | What lives there |
|---|---|
| `presentation-logic/cli/` | argparse CLI, JSON summary on stdout, exit codes (a job has no HTTP API) |
| `application-logic/services/` | `refresh_service` (download or `--zip-path`, then ingest, then prune) and `ingest_service` (the one-transaction upsert) |
| `application-logic/quality/` | data-quality gates, pure functions, checked before COMMIT |
| `db-logic/loaders/` | `downloader` (urllib, retries, atomic rename, retention) and `cricsheet_zip` (reads members in memory, never extracts) |
| `db-logic/transforms/` | `match_record`: validate a match file, extract indexed columns, zlib the exact bytes |
| `db-logic/repository/` + `db-logic/migrations/` | `raw_store` (SQLite access, migrations runner) and versioned `NNNN_*.sql` files |
| `shared/` | env config, logging, exceptions |

The underscored names (`db_logic` etc.) are committed symlinks so Python can import the hyphenated folders.

## Usage

Run from this folder (`cricstat/cricstat-pipeline/`):

```sh
python3 -m presentation_logic.cli full      # monthly: all_json.zip (~147 MB), detects removed matches
python3 -m presentation_logic.cli recent    # daily: recently_added_7_json.zip, upsert only
python3 -m presentation_logic.cli full --zip-path ../data/raw/all_json-20261005.zip   # no network
python3 -m presentation_logic.cli recent --quiet   # only warnings on stderr (Task Scheduler)
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
| 2 | a data-quality gate failed (rolled back) |

## Environment

Relative paths resolve against `CRICSTAT_HOME` (default: the `cricstat/` folder; `/cricstat` in the image).
See `.env.example`.

| Variable | Default |
|---|---|
| `CRICSTAT_HOME` | parent of `cricstat-pipeline/` |
| `CRICSTAT_DATA_DIR` | `data` |
| `CRICSTAT_RAW_ZIP_DIR` | `data/raw` |
| `CRICSTAT_RAW_DB` | `data/db/raw.sqlite` |
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

The Dockerfile (`docker/Dockerfile`, python:3.12-slim, non-root `appuser`) has not been
built yet. It expects `cricstat/data` and `cricstat/logs` mounted at `/cricstat/data` and `/cricstat/logs`.

## Data notes (first load, 2026-10-05)

- 22,983 matches, 2001-12-19 to 2026-09-17, all `data_version` 1.2.0; 0 parse failures.
- 25 match ids are not digits: `wi_*`, West Indies women's domestic matches (T20 Blaze,
  Women's Super50, 2019 and 2022). So match_id is *not* always an ESPNcricinfo id.
- About 4.0 GB of JSON compresses to 145 MB in `json_zlib`; the database is ~168 MB.

## Attribution

Match data from Cricsheet (cricsheet.org), used under the Open Data Commons Attribution License 1.0.
