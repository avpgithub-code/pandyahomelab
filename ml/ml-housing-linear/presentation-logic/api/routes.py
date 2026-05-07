import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import HTMLResponse

from presentation_logic.api.schemas import HealthResponse, PredictionRequest, PredictionResponse
from application_logic.services.prediction_service import PredictionService

router = APIRouter()
logger = logging.getLogger(__name__)

_service = PredictionService()

_UI_PATH = Path(__file__).parent / "ui.html"


@router.get("/", response_class=HTMLResponse)
async def demo_ui():
    return _UI_PATH.read_text()


@router.get("/health", response_model=HealthResponse)
async def health_check(x_request_id: Optional[str] = Header(None)):
    request_id = x_request_id or str(uuid.uuid4())
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0-alpha1",
        request_id=request_id,
    )


@router.post("/predict", response_model=PredictionResponse)
async def predict(
    request: PredictionRequest,
    x_request_id: Optional[str] = Header(None),
):
    request_id = x_request_id or str(uuid.uuid4())
    try:
        result = _service.predict(request.data)
        return PredictionResponse(
            prediction=result["prediction"],
            prediction_usd=result["prediction_usd"],
            unit=result["unit"],
            request_id=request_id,
        )
    except Exception as e:
        logger.error(f"[{request_id}] Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
