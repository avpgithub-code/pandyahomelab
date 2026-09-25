"""API routes for nlp-quora-randomforest: /, /about, /health, /predict, /model-info."""
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
    HealthResponse,
    ModelInfoResponse,
    PredictRequest,
    PredictResponse,
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


@router.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest, x_request_id: Optional[str] = Header(None)):
    """Trains lazily on the first call if eager warm-up hasn't finished;
    concurrent calls block on the train lock."""
    request_id = x_request_id or str(uuid.uuid4())
    try:
        result = _service.predict(request.text)
        return PredictResponse(**result, request_id=request_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Predict failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-info", response_model=ModelInfoResponse)
async def model_info():
    """Model metadata + (when trained) metrics + MLflow URL. Never trains."""
    try:
        return _service.get_model_info()
    except Exception as e:
        logger.error(f"Model info failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
