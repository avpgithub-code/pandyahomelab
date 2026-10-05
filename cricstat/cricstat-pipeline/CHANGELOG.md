# Changelog

## Unreleased

### Added (2026-10-05)
- Cricsheet ingestion: `full` (all_json.zip, removal detection) and `recent`
  (recently_added_7_json.zip) modes, idempotent sha256 upsert, one transaction per run.
- Raw SQLite store with versioned migrations (`0001_init.sql`): `matches_raw`,
  `ingest_runs`, `schema_version`; journal_mode=DELETE.
- Data-quality gates (parse failures, active-count drop) checked before commit.
- Downloader with User-Agent, timeouts, retry/backoff, atomic rename, dated retention.
- Tests (pytest, no network), ruff config, Dockerfile (not built), README.
- First real load: 22,983 matches; re-run on the same zip: 0 added / 0 updated.
