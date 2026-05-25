"""API routes for dl-lstm-forecast: /, /about, /health, /forecast, /history, /model-info."""
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
    ForecastRequest,
    ForecastResponse,
    HealthResponse,
    HistoryResponse,
    ModelInfoResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_service = PredictionService()
_UI_PATH = Path(__file__).parent / "ui.html"
_ABOUT_PATH = Path(__file__).parent / "about.json"


@router.get("/", response_class=HTMLResponse)
async def demo_ui():
    return _UI_PATH.read_text()


@router.get("/about")
async def about():
    return JSONResponse(content=json.loads(_ABOUT_PATH.read_text()))


@router.get("/health", response_model=HealthResponse)
async def health_check(x_request_id: Optional[str] = Header(None)):
    request_id = x_request_id or str(uuid.uuid4())
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0-alpha1",
        request_id=request_id,
    )


@router.get("/history", response_model=HistoryResponse)
async def history(x_request_id: Optional[str] = Header(None)):
    """Full historical series for the UI's background chart.

    Safe to call before warm-up completes — touches only db-logic, not the
    trained model.
    """
    request_id = x_request_id or str(uuid.uuid4())
    try:
        hist = _service.get_history()
        return HistoryResponse(
            dates=hist["dates"],
            trips=hist["trips"],
            min_anchor=hist["min_anchor"],
            max_anchor=hist["max_anchor"],
            request_id=request_id,
        )
    except Exception as e:
        logger.error(f"[{request_id}] History failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forecast", response_model=ForecastResponse)
async def forecast(
    request: ForecastRequest,
    x_request_id: Optional[str] = Header(None),
):
    """Autoregressive 14-day forecast (MC-Dropout band) anchored at the
    requested date. Trains the model lazily on the first call if eager
    warm-up hasn't finished yet; concurrent calls block on the train lock."""
    request_id = x_request_id or str(uuid.uuid4())
    try:
        result = _service.forecast(
            anchor_date=request.anchor_date,
            horizon=request.horizon,
            n_samples=request.n_samples,
        )
        return ForecastResponse(
            anchor_date=result["anchor_date"],
            horizon=result["horizon"],
            window_size=result["window_size"],
            points=result["points"],
            request_id=request_id,
        )
    except ValueError as e:
        # Anchor out of range, invalid args — surface as 400, not 500.
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Forecast failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-info", response_model=ModelInfoResponse)
async def model_info():
    """Model metadata + (when trained) metrics + MLflow URL. Does NOT
    trigger training — Cloudflare's 100s origin-response cap means we
    never auto-train from a metadata endpoint."""
    try:
        return _service.get_model_info()
    except Exception as e:
        logger.error(f"Model info failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
