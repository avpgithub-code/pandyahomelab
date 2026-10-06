# cricstat-api

GET-only statistics API for cricstat (contract: [`../docs/F5-api-contract.md`](../docs/F5-api-contract.md)).
It reads the serving database that `cricstat-pipeline build` produces and never writes anything.

| | |
|---|---|
| Container | `cricstat-api` · always on · cricstat-network `172.25.0.10:8000` → host `127.0.0.1:8040` |
| Public path | `/cricket/api/` (Nginx strips the prefix; the app answers at `/v1/...`) |
| Runtime | Python 3.12 image (code also runs on the NAS host's 3.8 for tests) · FastAPI · one uvicorn worker |
| Data | `cricstat/data/db/` mounted **read-only as a directory** (a file mount would hide each new build) |

## Layers (ADR-013)

| Layer | What lives there |
|---|---|
| `presentation-logic/api/` | FastAPI app factory, routes, envelope, ETag/304, problem+json errors, warm-up |
| `application-logic/services/` | players, teams, meta services; `metrics.py` (ratio formulas mirroring the F4 views); `slugs.py` (public ids); `common.py` (filters, paging) |
| `db-logic/repository/` | `db.py` (read-only connection, reopen on swap, per-build cache, query time limit, scope SQL), `players_repo`, `teams_repo`, `meta_repo` |
| `shared/` | config, exceptions, logging |

## Endpoints (step P0.3)

| Endpoint | Notes |
|---|---|
| `GET /v1/health` | `{status, build_id, data_as_of}`; 503 `no_db` when there is no serving DB |
| `GET /v1/status` | Latest build + warnings, recent builds, last ingest runs, counts |
| `GET /v1/meta/scopes` · `/meta/competitions?featured=` · `/meta/metrics` | Filters and definitions |
| `GET /v1/search?q=&type=player\|team\|competition&gender=&limit=` | Ranked, with disambiguation facts |
| `GET /v1/players/{id}` · `/career` · `/years` · `/phases` · `/splits?by=` · `/innings` | `scope=` ALL (default), TEST, ODI, T20I, LEAGUES, a league slug… |
| `GET /v1/teams?gender=&type=` · `/teams/{slug}` · `/record` · `/results` · `/head-to-head` · `/home-away` · `/years` · `/top-players` | Team slug = name + men/women, e.g. `india-women` |
| `GET /openapi.json` | Schema. Swagger/ReDoc pages are off: they load scripts from a CDN, which the site's privacy promise rules out |

Additions to F5 (non-breaking): `GET /v1/teams` (team picker) and `GET /v1/teams/{slug}/years` (results by year).
Filters: `from`/`to` take `YYYY-MM-DD`, a year (`2023`) or a season (`2023-24` = 1 Jul 2023–30 Jun 2024).

Every response: `{"data": …, "meta": {data_as_of, build_id, filters, metrics, coverage, attribution, next?}}`.
`meta.metrics` comes from `semantic_catalog` (or `metrics.DEFINITIONS` for groupings no view covers).
Headers: `ETag: "<build_id>"` (304 on `If-None-Match`), `Cache-Control: public, max-age=300, stale-while-revalidate=3600`,
`X-Response-Time-ms`. Errors: `application/problem+json` — 400 bad filter, 404 unknown id, 422 filters that
can't combine (e.g. phases with TEST), 503 no DB or a query over the 10 s limit.

## How it stays correct and fast

- **Ratios:** the career view (`v_player_*`), team record and head to head come straight from the F4 views. Years,
  phases, splits and windows use `metrics.py`, which mirrors the view formulas; tests compare the two.
- **Scopes:** `Scopes.clause()` selects exactly the matches the pipeline's marts count (a test checks every scope).
- **New builds:** the pipeline replaces the file, never edits it, so connections are `immutable=1`; each request
  checks the inode and reopens on a change. A background thread reads each new file once so the OS page cache
  holds it (cold random reads on the NAS disks took seconds; warm queries take milliseconds).

## Develop

```sh
python3 -m pip install --user -r requirements-dev.txt
python3 -m ruff check .
python3 -m pytest -q        # builds a small dataset with ../cricstat-pipeline in subprocesses; no network
CRICSTAT_HOME=.. python3 -m uvicorn presentation_logic.api.main:app --port 8040   # against the real DB
```

## Deploy

CI builds and publishes `ghcr.io/avpgithub-code/cricstat-api` (approval gate `nas-production`);
`deployment/cricstat/cd-pull.sh` pulls it, smoke-tests it on the NAS against the real DB, restarts the
container, health-checks it and rolls back on failure. Never `docker compose build` on the NAS.

## Attribution

Match data from Cricsheet (cricsheet.org), used under the Open Data Commons Attribution License 1.0.
