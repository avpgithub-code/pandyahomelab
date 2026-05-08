"""API routes for ml-titanic-automl."""
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import HTMLResponse
from datetime import datetime
from typing import Optional
import uuid

from .schemas import (
    HealthResponse, PredictionRequest, PredictionResponse, ModelInfoResponse
)

router = APIRouter()

# Single shared service instance — trained once on first request
_service = None


def _get_service():
    global _service
    if _service is None:
        from application_logic.services.prediction_service import PredictionService
        _service = PredictionService()
    return _service


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
async def predict(request: PredictionRequest, x_request_id: Optional[str] = Header(None)):
    request_id = x_request_id or str(uuid.uuid4())
    try:
        svc = _get_service()
        result = svc.predict(request.model_dump())
        return PredictionResponse(**result, request_id=request_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-info", response_model=ModelInfoResponse)
async def model_info():
    try:
        svc = _get_service()
        return ModelInfoResponse(**svc.get_model_info())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_class=HTMLResponse)
async def ui():
    import os
    ui_path = os.path.join(os.path.dirname(__file__), "ui.html")
    with open(ui_path) as f:
        return HTMLResponse(content=f.read())
