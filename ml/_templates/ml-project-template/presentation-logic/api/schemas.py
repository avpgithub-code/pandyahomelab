"""Pydantic request/response schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status: 'healthy' or 'unhealthy'")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="API version")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class PredictionRequest(BaseModel):
    """Prediction request."""
    data: List[float] = Field(..., description="Input features for prediction")
    model_version: Optional[str] = Field(None, description="Model version to use")


class PredictionResponse(BaseModel):
    """Prediction response."""
    prediction: float = Field(..., description="Predicted value")
    confidence: float = Field(..., description="Prediction confidence (0-1)")
    request_id: Optional[str] = Field(None, description="Request tracking ID")
