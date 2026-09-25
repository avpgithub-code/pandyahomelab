"""FastAPI application factory for nlp-quora-randomforest.

Lifespan handler runs the eager warm-up in a background asyncio.to_thread, so
uvicorn binds immediately and the model (plus any spaCy / gensim assets) loads
out-of-band before the first visitor arrives (Phase 2a lesson).
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI

from presentation_logic.api.routes import VERSION, _service, router

logger = logging.getLogger(__name__)


async def _eager_warm_up() -> None:
    """Train in a background thread. Idempotent — PredictionService._train_lock
    makes a /predict arriving mid-warm-up wait instead of training twice.

    print(flush=True) rather than logger.info: uvicorn leaves the root logger at
    WARNING, and these lines should show in `docker logs`.
    """
    print("[warm-up] training begins in background...", flush=True)
    try:
        await asyncio.to_thread(_service.train)
        info = _service.get_model_info()
        print(
            f"[warm-up] Done. metrics={info.get('metrics')} run_id={info.get('run_id')}",
            flush=True,
        )
    except Exception as e:
        logger.warning(f"[warm-up] Failed: {e}. First /predict will train on demand.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[{datetime.utcnow().isoformat()}] nlp-quora-randomforest service starting")
    # Keep the task on app.state so it isn't garbage-collected mid-flight.
    app.state.warmup_task = asyncio.create_task(_eager_warm_up())
    yield
    print(f"[{datetime.utcnow().isoformat()}] nlp-quora-randomforest service shutting down")
    if not app.state.warmup_task.done():
        app.state.warmup_task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title="nlp-quora-randomforest",
        description="Duplicate question pair detector on Quora Question Pairs — bag-of-words + 22 engineered features into a Random Forest",
        version=VERSION,
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
