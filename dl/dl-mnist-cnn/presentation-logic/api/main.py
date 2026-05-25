"""FastAPI application factory for dl-mnist-cnn.

Uses the modern lifespan handler (not deprecated @app.on_event) so the
eager warm-up runs in a background asyncio.to_thread — uvicorn binds
immediately and the ~8 min CNN training happens out-of-band. After
warm-up completes, /predict returns in ms instead of triggering the
8-min cold-start path that would 524 through Cloudflare's 100s limit.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI

from presentation_logic.api.routes import _service, router

logger = logging.getLogger(__name__)


async def _eager_warm_up() -> None:
    """Train the CNN in a background thread. Idempotent — protected by
    PredictionService._train_lock — so a /predict arriving mid-warm-up
    blocks-and-waits instead of starting a duplicate training.

    Lifecycle messages use print(flush=True) instead of logger.info so they
    appear in docker logs without setting up app-level logging.basicConfig
    (uvicorn doesn't touch the root logger, so logger.info would be filtered
    at WARNING by default). Failure path keeps logger.warning — that level
    is visible regardless of basicConfig.
    """
    print("[warm-up] CNN training begins in background...", flush=True)
    try:
        await asyncio.to_thread(_service.train)
        acc = _service.get_model_info().get("metrics", {}).get("accuracy")
        print(f"[warm-up] Done. Test accuracy: {acc}", flush=True)
    except Exception as e:
        logger.warning(
            f"[warm-up] Failed: {e}. First /predict will train on demand."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[{datetime.utcnow().isoformat()}] dl-mnist-cnn service starting")
    # asyncio.create_task returns a task ref; keep it on app.state to prevent
    # Python from GCing it mid-flight (asyncio's docs explicitly warn about
    # "fire-and-forget" tasks being garbage-collected before they complete).
    app.state.warmup_task = asyncio.create_task(_eager_warm_up())
    yield
    print(f"[{datetime.utcnow().isoformat()}] dl-mnist-cnn service shutting down")
    # If the container is killed mid-warm-up, cancel cleanly.
    if not app.state.warmup_task.done():
        app.state.warmup_task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title="dl-mnist-cnn",
        description="Handwritten digit classification (PyTorch CNN, MNIST) with HTML5 canvas UI",
        version="1.0.0-alpha1",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
