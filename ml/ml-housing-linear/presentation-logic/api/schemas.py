from typing import Dict, List, Optional
from pydantic import BaseModel, Field, validator


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="API version")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class PredictionRequest(BaseModel):
    data: List[float] = Field(
        ...,
        description="8 California Housing features: MedInc, HouseAge, AveRooms, AveBedrms, Population, AveOccup, Latitude, Longitude",
    )

    @validator("data")
    def validate_features(cls, v):
        if len(v) != 8:
            raise ValueError(
                "Exactly 8 features required: MedInc, HouseAge, AveRooms, AveBedrms, Population, AveOccup, Latitude, Longitude"
            )
        return v


class PredictionResponse(BaseModel):
    prediction: float = Field(..., description="Predicted median house value (in $100,000s)")
    prediction_usd: str = Field(..., description="Human-readable price e.g. '$245,000'")
    unit: str = Field(..., description="Unit of the raw prediction value")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class ModelInfoResponse(BaseModel):
    model_type: str
    dataset: str
    n_samples: int
    n_features: int
    parameters: Dict
    metrics: Dict
    run_id: Optional[str] = None
    experiment_id: Optional[str] = None
    mlflow_url: Optional[str] = None
