"""Pydantic request/response schemas for dl-mnist-cnn API."""
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="API version")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class PredictionRequest(BaseModel):
    pixels: List[float] = Field(
        ...,
        description="Flat list of 784 grayscale pixel values (0-255), row-major 28x28 image",
    )

    @field_validator("pixels")
    @classmethod
    def validate_pixels(cls, v):
        if len(v) != 784:
            raise ValueError("Exactly 784 pixel values required (28x28 image)")
        if any(p < 0 or p > 255 for p in v):
            raise ValueError("Pixel values must be in range 0-255")
        return v


class PredictionResponse(BaseModel):
    prediction: int = Field(..., description="Predicted digit (0-9)")
    digit: str = Field(..., description="Predicted digit as string")
    confidence: float = Field(..., description="Softmax confidence for the predicted class (0-1)")
    probabilities: Dict[str, float] = Field(..., description="Per-digit softmax probabilities")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class ModelInfoResponse(BaseModel):
    # `model_*` field names collide with pydantic v2's reserved namespace
    # (used for things like `model_validate`, `model_dump`) — opt out so the
    # `model_type` / `model` etc. fields can keep their natural names.
    model_config = ConfigDict(protected_namespaces=())

    model_type: str
    architecture: str
    dataset: str
    classes: List[str]
    parameters: Dict
    metrics: Dict
    metrics_display: Optional[Dict] = None
    split: Optional[Dict] = None
    run_id: Optional[str] = None
    experiment_id: Optional[str] = None
    mlflow_url: Optional[str] = None
