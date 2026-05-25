"""FastAPI application factory for dl-lstm-forecast.

Uses the modern lifespan handler (not deprecated @app.on_event) so the
eager warm-up runs in a background asyncio.to_thread — uvicorn binds
immediately and LSTM training (~10s on full CitiBike CSV) happens out-
of-band. After warm-up completes, /forecast returns in ~2s for a 14-day
14-step × 30-MC-sample autoregressive rollout instead of triggering a
cold-start that would also need to train first.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI

from presentation_logic.api.routes import _service, router

logger = logging.getLogger(__name__)


async def _eager_warm_up() -> None:
    """Train the LSTM in a background thread. Idempotent — protected by
    PredictionService._train_lock — so a /forecast arriving mid-warm-up
    blocks-and-waits instead of starting a duplicate training.

    Lifecycle messages use print(flush=True) instead of logger.info so they
    appear in docker logs without setting up app-level logging.basicConfig
    (uvicorn doesn't touch the root logger, so logger.info would be filtered
    at WARNING by default). Same pattern as dl-mnist-cnn — see
    [[phase_2a_complete]].
    """
    print("[warm-up] LSTM training begins in background...", flush=True)
    try:
        await asyncio.to_thread(_service.train)
        m = _service.get_model_info().get("metrics", {})
        mape = m.get("test_mape")
        rmse = m.get("test_rmse")
        epochs = m.get("epochs_run")
        print(
            f"[warm-up] Done. test_mape={mape}, test_rmse={rmse}, epochs_run={epochs}",
            flush=True,
        )
    except Exception as e:
        logger.warning(
            f"[warm-up] Failed: {e}. First /forecast will train on demand."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[{datetime.utcnow().isoformat()}] dl-lstm-forecast service starting")
    # asyncio.create_task returns a task ref; keep it on app.state to prevent
    # Python from GCing it mid-flight (asyncio's docs explicitly warn about
    # "fire-and-forget" tasks being garbage-collected before they complete).
    app.state.warmup_task = asyncio.create_task(_eager_warm_up())
    yield
    print(f"[{datetime.utcnow().isoformat()}] dl-lstm-forecast service shutting down")
    if not app.state.warmup_task.done():
        app.state.warmup_task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title="dl-lstm-forecast",
        description="LSTM time-series forecaster on NYC CitiBike daily ride counts",
        version="1.0.0-alpha1",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
