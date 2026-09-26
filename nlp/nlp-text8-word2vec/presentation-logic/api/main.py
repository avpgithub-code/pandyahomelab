"""FastAPI application factory for nlp-text8-word2vec.

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
    print("[warm-up] loading embeddings in background...", flush=True)
    try:
        await asyncio.to_thread(_service.train)
        info = _service.get_model_info()
        print(
            f"[warm-up] Done. models={list((info.get('metrics') or {}).keys())}",
            flush=True,
        )
    except Exception as e:
        logger.warning(f"[warm-up] Failed: {e}. Queries will retry the load.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[{datetime.utcnow().isoformat()}] nlp-text8-word2vec service starting")
    # Keep the task on app.state so it isn't garbage-collected mid-flight.
    app.state.warmup_task = asyncio.create_task(_eager_warm_up())
    yield
    print(f"[{datetime.utcnow().isoformat()}] nlp-text8-word2vec service shutting down")
    if not app.state.warmup_task.done():
        app.state.warmup_task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title="nlp-text8-word2vec",
        description="Word2Vec explorer: CBOW vs skip-gram vs fastText trained on text8, GloVe 6B as reference — neighbours, analogies, similarity and a 2-D map",
        version=VERSION,
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
