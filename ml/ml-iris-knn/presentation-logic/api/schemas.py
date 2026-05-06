"""Pydantic request/response schemas for Iris KNN API."""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, validator


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="API version")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class PredictionRequest(BaseModel):
    data: List[float] = Field(..., description="4 iris features: sepal_length, sepal_width, petal_length, petal_width")

    @validator("data")
    def validate_features(cls, v):
        if len(v) != 4:
            raise ValueError("Exactly 4 features required: sepal_length, sepal_width, petal_length, petal_width")
        if any(f <= 0 for f in v):
            raise ValueError("All feature values must be positive")
        return v


class PredictionResponse(BaseModel):
    prediction: int = Field(..., description="Predicted class (0=setosa, 1=versicolor, 2=virginica)")
    species: str = Field(..., description="Predicted species name")
    confidence: float = Field(..., description="Prediction confidence (0-1)")
    probabilities: Dict[str, float] = Field(..., description="Per-class probabilities")
    request_id: Optional[str] = Field(None, description="Request tracking ID")
