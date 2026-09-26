"""API routes for nlp-text8-word2vec: /, /about, /health, /neighbors, /analogy, /similarity, /map, /model-info."""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from application_logic.services.prediction_service import PredictionService
from presentation_logic.api.schemas import (
    AnalogyRequest,
    HealthResponse,
    MapRequest,
    ModelInfoResponse,
    NeighborsRequest,
    SimilarityRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)

VERSION = "0.1.0"

_service = PredictionService()
_UI_PATH = Path(__file__).parent / "ui.html"
_ABOUT_PATH = Path(__file__).parent / "about.json"


@router.get("/", response_class=HTMLResponse)
async def demo_ui():
    return _UI_PATH.read_text()


@router.get("/about")
async def about():
    """Static About content. Live numbers come from /model-info — the drawer
    substitutes {{tokens}} client-side."""
    return JSONResponse(content=json.loads(_ABOUT_PATH.read_text()))


@router.get("/health", response_model=HealthResponse)
async def health_check(x_request_id: Optional[str] = Header(None)):
    request_id = x_request_id or str(uuid.uuid4())
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version=VERSION,
        request_id=request_id,
    )


def _run(fn, *args):
    """Models not trained yet -> 503 with the fix; anything else -> 500."""
    try:
        return fn(*args)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/neighbors")
async def neighbors(request: NeighborsRequest):
    return _run(_service.neighbors, request.word, request.topn)


@router.post("/analogy")
async def analogy(request: AnalogyRequest):
    return _run(_service.analogy, request.a, request.b, request.c)


@router.post("/similarity")
async def similarity(request: SimilarityRequest):
    return _run(_service.similarity, request.w1, request.w2)


@router.post("/map")
async def word_map(request: MapRequest):
    return _run(_service.project, request.words)


@router.get("/model-info", response_model=ModelInfoResponse)
async def model_info():
    """Model metadata + (when trained) metrics + MLflow URL. Never trains."""
    try:
        return _service.get_model_info()
    except Exception as e:
        logger.error(f"Model info failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
