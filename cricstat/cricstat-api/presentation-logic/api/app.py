"""cricstat-api: GET-only stats API over the serving DB (F5). Answers at its own root (/v1/...);
Nginx maps /cricket/api/ onto it.

Every response uses one envelope {data, meta} carrying the provenance (data_as_of, build_id,
filters, metric definitions, coverage, attribution). Errors are application/problem+json.
Caching: ETag = build id (the data changes once a day), Cache-Control public, 304 on a match.
"""
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlencode

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from application_logic.services import (
    admin_service,
    forecast_service,
    matches_service,
    meta_service,
    players_service,
    teams_service,
)
from application_logic.services.common import catalog_defs, team_slugs
from db_logic.repository import meta_repo
from db_logic.repository.db import QueryTimeout, ServingDB
from db_logic.repository.forecast_db import ForecastDB
from presentation_logic.api import pages
from shared.config import ATTRIBUTION, COVERAGE, Config
from shared.exceptions import ApiError, NoData, NotFound
from shared.logger import get_logger, setup_logging

log = get_logger("http")
PROBLEM = "application/problem+json"


def create_app(cfg: Optional[Config] = None) -> FastAPI:
    cfg = cfg or Config()
    setup_logging(cfg.LOG_LEVEL)
    db = ServingDB(cfg.SERVING_DB)
    fdb = ForecastDB(cfg.FORECAST_DB)          # P1 predictor output; may be absent (→ 503 there)

    @asynccontextmanager
    async def lifespan(app):
        warm_up(db)                        # first requests shouldn't pay for cold disk reads
        stop = threading.Event()
        threading.Thread(target=cache_watcher, args=(db, stop), daemon=True,
                         name="cache-watcher").start()
        yield
        stop.set()
    # Swagger/ReDoc pages load scripts from a CDN, which the site's privacy promise rules out;
    # the schema itself is served, and a self-hosted docs page comes with the web pages.
    app = FastAPI(title="cricstat API", version="1.0.0", docs_url=None, redoc_url=None,
                  openapi_url="/openapi.json", lifespan=lifespan,
                  description="Cricket statistics from Cricsheet ball-by-ball data. " + ATTRIBUTION)
    app.state.db, app.state.fdb, app.state.cfg = db, fdb, cfg

    def build() -> dict:
        return db.cached("build", lambda: meta_repo.latest_build(db) or {})

    def envelope(request: Request, data, metrics: dict, more: bool = False,
                 extra_filters: Optional[dict] = None, etag_extra: Optional[str] = None,
                 coverage: str = COVERAGE) -> Response:
        b = build()
        # Forecast responses change with the forecast id as well as the build.
        etag = '"%s%s"' % (b.get("build_id"), "-" + etag_extra if etag_extra else "")
        headers = {"ETag": etag, "Cache-Control": "public, max-age=%d, stale-while-revalidate=%d"
                   % (cfg.CACHE_MAX_AGE, cfg.CACHE_SWR)}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        params = dict(request.query_params)
        meta = {"data_as_of": b.get("data_as_of"), "build_id": b.get("build_id"),
                "filters": dict(params, **(extra_filters or {})), "metrics": metrics,
                "coverage": coverage, "attribution": ATTRIBUTION}
        if more:
            limit = int(params.get("limit") or 20)
            params["offset"] = str(int(params.get("offset") or 0) + limit)
            meta["next"] = "%s?%s" % (request.url.path, urlencode(params))
        return JSONResponse({"data": data, "meta": meta}, headers=headers)

    def problem(status: int, title: str, detail: str) -> JSONResponse:
        return JSONResponse({"type": "about:blank", "title": title, "status": status,
                             "detail": detail}, status_code=status, media_type=PROBLEM)

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return problem(exc.status, exc.title, exc.detail)

    @app.exception_handler(QueryTimeout)
    async def timeout(request: Request, exc: QueryTimeout):
        log.warning("query timeout: %s", request.url)
        return problem(503, "Query took too long", "Try a narrower filter.")

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, exc: RequestValidationError):
        msgs = ["%s: %s" % (".".join(str(x) for x in e["loc"][1:]), e["msg"])
                for e in exc.errors()]
        return problem(400, "Bad filter", "; ".join(msgs))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return problem(exc.status_code, "Not found" if exc.status_code == 404 else "Error",
                       str(exc.detail))

    @app.middleware("http")
    async def timing(request: Request, call_next):
        t0 = time.monotonic()
        response = await call_next(request)
        response.headers["X-Response-Time-ms"] = "%.0f" % ((time.monotonic() - t0) * 1000)
        return response

    pages.register(app, cfg)               # /pages/...: server-rendered player/team heads (P0.6)

    # ── Meta and status ──
    @app.get("/v1/health")
    def health():
        try:
            return meta_service.health(db)
        except NoData as exc:
            return JSONResponse({"status": "no_db", "detail": exc.detail}, status_code=503)

    @app.get("/v1/status")
    def status(request: Request):
        return envelope(request, *meta_service.status(db, cfg.RAW_DB))

    @app.get("/v1/meta/scopes")
    def scopes(request: Request):
        return envelope(request, *meta_service.scopes(db))

    @app.get("/v1/meta/competitions")
    def competitions(request: Request, featured: Optional[bool] = None):
        return envelope(request, *meta_service.competitions(db, featured))

    @app.get("/v1/meta/metrics")
    def metric_list(request: Request):
        return envelope(request, *meta_service.metric_list(db))

    # ── Search ──
    @app.get("/v1/search")
    def search(request: Request, q: Optional[str] = None, type: Optional[str] = None,
               gender: Optional[str] = None, limit: Optional[int] = Query(None, ge=1, le=50)):
        return envelope(request, *meta_service.search(db, q, type, gender, limit))

    # ── Players ──
    @app.get("/v1/players/{player_id}")
    def player(request: Request, player_id: str):
        return envelope(request, *players_service.profile(db, player_id))

    @app.get("/v1/players/{player_id}/career")
    def career(request: Request, player_id: str, scope: str = "ALL"):
        return envelope(request, *players_service.career(db, player_id, scope),
                        extra_filters={"scope": scope})

    @app.get("/v1/players/{player_id}/years")
    def player_years(request: Request, player_id: str, scope: str = "ALL"):
        return envelope(request, *players_service.years(db, player_id, scope),
                        extra_filters={"scope": scope})

    @app.get("/v1/players/{player_id}/phases")
    def phases(request: Request, player_id: str, scope: str = "T20I"):
        return envelope(request, *players_service.phases(db, player_id, scope),
                        extra_filters={"scope": scope})

    @app.get("/v1/players/{player_id}/splits")
    def splits(request: Request, player_id: str, by: str = "opponent", scope: str = "ALL"):
        return envelope(request, *players_service.splits(db, player_id, scope, by),
                        extra_filters={"scope": scope, "by": by})

    @app.get("/v1/players/{player_id}/innings")
    def player_innings(request: Request, player_id: str, scope: str = "ALL",
                       date_from: Optional[str] = Query(None, alias="from"),
                       date_to: Optional[str] = Query(None, alias="to"),
                       limit: Optional[int] = None, offset: Optional[int] = None):
        data, defs, more = players_service.innings(db, player_id, scope, date_from, date_to,
                                                   limit, offset)
        return envelope(request, data, defs, more, extra_filters={"scope": scope})

    # ── Teams ──
    @app.get("/v1/teams")
    def teams(request: Request, gender: Optional[str] = None, type: Optional[str] = None):
        return envelope(request, *teams_service.list_teams(db, gender, type))

    @app.get("/v1/records/teams")
    def team_records(request: Request, scope: Optional[str] = None, gender: Optional[str] = None,
                     type: Optional[str] = None,
                     date_from: Optional[str] = Query(None, alias="from"),
                     date_to: Optional[str] = Query(None, alias="to")):
        return envelope(request, *teams_service.records(db, scope, gender, type, date_from,
                                                        date_to))

    @app.get("/v1/teams/{slug}")
    def team(request: Request, slug: str):
        return envelope(request, *teams_service.team(db, slug))

    @app.get("/v1/teams/{slug}/record")
    def team_record(request: Request, slug: str, scope: Optional[str] = None,
                    date_from: Optional[str] = Query(None, alias="from"),
                    date_to: Optional[str] = Query(None, alias="to")):
        return envelope(request, *teams_service.record(db, slug, scope, date_from, date_to))

    @app.get("/v1/teams/{slug}/results")
    def team_results(request: Request, slug: str, scope: Optional[str] = None,
                     date_from: Optional[str] = Query(None, alias="from"),
                     date_to: Optional[str] = Query(None, alias="to"),
                     limit: Optional[int] = None, offset: Optional[int] = None):
        data, defs, more = teams_service.results(db, slug, scope, date_from, date_to, limit,
                                                 offset)
        return envelope(request, data, defs, more)

    @app.get("/v1/teams/{slug}/head-to-head")
    def h2h(request: Request, slug: str, scope: Optional[str] = None,
            opponent: Optional[str] = None):
        return envelope(request, *teams_service.head_to_head(db, slug, scope, opponent))

    @app.get("/v1/teams/{slug}/home-away")
    def home_away(request: Request, slug: str, scope: Optional[str] = None):
        return envelope(request, *teams_service.home_away(db, slug, scope))

    @app.get("/v1/teams/{slug}/years")
    def team_years(request: Request, slug: str, scope: Optional[str] = None):
        return envelope(request, *teams_service.years(db, slug, scope))

    @app.get("/v1/teams/{slug}/top-players")
    def top_players(request: Request, slug: str, scope: Optional[str] = None,
                    metric: str = "runs", date_from: Optional[str] = Query(None, alias="from"),
                    date_to: Optional[str] = Query(None, alias="to"),
                    limit: Optional[int] = None):
        return envelope(request, *teams_service.top_players(db, slug, scope, metric, date_from,
                                                            date_to, limit))

    # ── Matches and leaderboards ──
    @app.get("/v1/matches")
    def match_list(request: Request, scope: Optional[str] = None, gender: Optional[str] = None,
                   team: Optional[str] = None,
                   date_from: Optional[str] = Query(None, alias="from"),
                   date_to: Optional[str] = Query(None, alias="to"),
                   limit: Optional[int] = None, offset: Optional[int] = None):
        data, defs, more = matches_service.list_matches(db, scope, gender, team, date_from,
                                                        date_to, limit, offset)
        return envelope(request, data, defs, more)

    @app.get("/v1/leaderboards/{kind}")
    def leaderboard(request: Request, kind: str, metric: Optional[str] = None,
                    scope: Optional[str] = None, gender: Optional[str] = None,
                    date_from: Optional[str] = Query(None, alias="from"),
                    date_to: Optional[str] = Query(None, alias="to"),
                    limit: Optional[int] = None):
        if kind not in ("batting", "bowling"):
            raise NotFound("leaderboards are batting or bowling")
        metric = metric or ("runs" if kind == "batting" else "wickets")
        return envelope(request, *matches_service.leaderboard(db, kind, metric, scope, gender,
                                                              date_from, date_to, limit))

    # ── ODI World Cup 2027 predictor (P1.5; data written by cricstat-models) ──
    PREDICTOR_COVERAGE = (COVERAGE + "; for the predictor, Afghanistan's ODI results come from a "
                          "reviewed results list (Wikipedia), rated by the same rule")

    def fenvelope(request: Request, data_defs) -> Response:
        data, defs = data_defs
        return envelope(request, forecast_service.json_safe(data), defs,
                        etag_extra=forecast_service.etag(fdb), coverage=PREDICTOR_COVERAGE)

    @app.get("/v1/forecasts/{tournament}/latest")
    def forecast_latest(request: Request, tournament: str):
        return fenvelope(request, forecast_service.latest(db, fdb, tournament))

    @app.get("/v1/forecasts/{tournament}/history")
    def forecast_history(request: Request, tournament: str, team: Optional[str] = None):
        return fenvelope(request, forecast_service.history(db, fdb, tournament, team))

    @app.get("/v1/forecasts/{tournament}/fixtures")
    def forecast_fixtures(request: Request, tournament: str):
        return fenvelope(request, forecast_service.fixtures(db, fdb, tournament))

    @app.get("/v1/ratings")
    def rating_list(request: Request, scope: str = "ODI", gender: str = "male"):
        return fenvelope(request, forecast_service.ratings(db, fdb, scope, gender))

    @app.get("/v1/ratings/{slug}/history")
    def rating_history(request: Request, slug: str, scope: str = "ODI"):
        return fenvelope(request, forecast_service.rating_history(db, fdb, slug, scope))

    @app.get("/v1/models/predictor/backtest")
    def predictor_backtest(request: Request):
        return fenvelope(request, forecast_service.backtest(fdb))

    # ── Internal admin views (P0.3b) — for the admin portal only; Nginx keeps them off the public
    #    site. Not cached: job status changes independently of the build id.
    def admin(data_defs):
        data, defs = data_defs
        b = build()
        return JSONResponse({"data": data, "meta": {"build_id": b.get("build_id"),
                                                    "data_as_of": b.get("data_as_of"),
                                                    "metrics": defs}},
                            headers={"Cache-Control": "no-store"})

    @app.get("/v1/admin/jobs", include_in_schema=False)
    def admin_jobs():
        data, defs = admin_service.jobs(db, cfg.RAW_DB, cfg.LOG_DIR, cfg.NAS_UTC_OFFSET)
        data["forecast"] = forecast_service.admin_block(fdb)      # P1 predictor job
        return admin((data, defs))

    @app.get("/v1/admin/overview", include_in_schema=False)
    def admin_overview():
        return admin(admin_service.overview(db, cfg.SERVING_DB, cfg.RAW_DB))

    @app.get("/v1/admin/golden", include_in_schema=False)
    def admin_golden():
        return admin(admin_service.golden_figures(db, cfg.GOLDEN_SELECTION))

    return app


def warm_up(db: ServingDB) -> None:
    """Fill the per-build caches (scopes, team slugs, catalog, build). No DB yet → skip quietly."""
    t0 = time.monotonic()
    try:
        db.scopes()
        team_slugs(db)
        catalog_defs(db, [])
        db.cached("build", lambda: meta_repo.latest_build(db) or {})
    except NoData:
        log.warning("no serving DB yet; warm-up skipped")
        return
    log.info("warm-up done in %.0f ms", (time.monotonic() - t0) * 1000)


def read_through(path: str, chunk: int = 8 << 20, pause: float = 0.02) -> float:
    """Read the file once, sequentially, so the OS page cache holds it (random reads of a cold
    file on the NAS disks took seconds; warm, the same queries take milliseconds)."""
    t0 = time.monotonic()
    with open(path, "rb") as f:
        while f.read(chunk):
            time.sleep(pause)              # stay gentle on the disks
    return time.monotonic() - t0


def cache_watcher(db: ServingDB, stop: threading.Event, every: float = 60.0) -> None:
    """On startup and after each build swap (new inode): page-cache the file, refill caches."""
    seen = None
    while not stop.is_set():
        try:
            ino = os.stat(db.path).st_ino
            if ino != seen:
                seen = ino
                log.info("new serving DB (inode %s): read-through took %.0fs", ino,
                         read_through(db.path))
                warm_up(db)
        except OSError as exc:
            log.warning("cache watcher: %s", exc)
        stop.wait(every)
