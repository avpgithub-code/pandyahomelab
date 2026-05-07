"""API routes: health check, prediction, training endpoints."""
from fastapi import APIRouter, HTTPException, Header
from datetime import datetime
from typing import Optional
import uuid

from .schemas import HealthResponse, PredictionRequest, PredictionResponse
from ...shared.logger import logger
from ...shared.config import get_config

router = APIRouter()
config = get_config()


@router.get("/health", response_model=HealthResponse)
async def health_check(x_request_id: Optional[str] = Header(None)):
    """Liveness and readiness probe for Kubernetes/Docker."""
    request_id = x_request_id or str(uuid.uuid4())
    logger.info(f"[{request_id}] Health check", extra={"request_id": request_id})

    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        request_id=request_id,
    )


@router.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest, x_request_id: Optional[str] = Header(None)):
    """Make a prediction using trained model."""
    request_id = x_request_id or str(uuid.uuid4())
    logger.info(
        f"[{request_id}] Prediction request",
        extra={"request_id": request_id, "data": request.data},
    )

    try:
        # TODO: Import and use predictor service
        # from ...application_logic.services.prediction_service import PredictionService
        # predictor = PredictionService()
        # result = await predictor.predict(request.data)

        result = {"prediction": 0.5, "confidence": 0.95}

        logger.info(
            f"[{request_id}] Prediction successful",
            extra={"request_id": request_id, "result": result},
        )

        return PredictionResponse(
            prediction=result["prediction"],
            confidence=result["confidence"],
            request_id=request_id,
        )
    except Exception as e:
        logger.error(
            f"[{request_id}] Prediction failed: {str(e)}",
            extra={"request_id": request_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail=str(e))
