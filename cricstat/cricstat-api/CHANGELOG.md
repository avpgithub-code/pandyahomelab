# Changelog

## Unreleased

### Added (2026-10-06)
- GET-only FastAPI service over the serving DB (F5): health, status, meta (scopes, competitions,
  metrics), search, players (profile, career, years, phases, splits, innings) and teams (list,
  identity, record, results, head to head, home/away, years, top players).
- One response envelope with provenance (data_as_of, build_id, filters, metric definitions,
  coverage, attribution); problem+json errors; ETag = build id with 304s; Cache-Control.
- Read-only, immutable SQLite connections reopened when the pipeline swaps in a new build;
  process-wide per-build caches, startup warm-up and a page-cache read-through of each new file.
- Per-query time limit (10 s) and limit ≤ 100 paging.
- Tests run the real pipeline on a synthetic dataset (no network), including a live swap.
