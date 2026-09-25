"""Pydantic request/response schemas for the nlp-quora-randomforest API."""
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="API version")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class PredictRequest(BaseModel):
    question1: str = Field(..., min_length=1, max_length=1000, description="First question")
    question2: str = Field(..., min_length=1, max_length=1000, description="Second question")


class PipelineStep(BaseModel):
    step: str = Field(..., description="Preprocessing step name")
    text: str = Field(..., description="Text after this step")


class PredictResponse(BaseModel):
    probability: float = Field(..., description="P(duplicate), 0-1")
    threshold: float = Field(..., description="Threshold behind `label`; the UI slider moves it")
    label: str = Field(..., description="'Duplicate' or 'Not duplicate' at `threshold`")
    features: Dict[str, Dict[str, float]] = Field(
        ..., description="The 22 engineered feature values, grouped basic/token/length/fuzzy"
    )
    pipeline: Dict[str, List[PipelineStep]] = Field(
        ..., description="Each question after every preprocessing step"
    )
    request_id: Optional[str] = None


class ModelInfoResponse(BaseModel):
    # `model_*` field names collide with pydantic v2's reserved namespace;
    # opt out so they keep their natural names.
    model_config = ConfigDict(protected_namespaces=())

    model_type: str
    architecture: str
    dataset: str
    target: str
    parameters: Dict
    preprocessing: Dict
    features: Dict
    metrics: Dict
    metrics_display: Optional[Dict] = None
    confusion_matrix: Optional[Dict] = None
    split: Optional[Dict] = None
    training: Optional[Dict] = None
    run_id: Optional[str] = None
    experiment_id: Optional[str] = None
    mlflow_url: Optional[str] = None
