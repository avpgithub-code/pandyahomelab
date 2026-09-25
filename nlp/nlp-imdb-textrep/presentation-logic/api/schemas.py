"""Pydantic request/response schemas for the nlp-imdb-textrep API."""
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="API version")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Any text, e.g. a movie review")


class PipelineStep(BaseModel):
    step: str = Field(..., description="Preprocessing step name")
    text: str = Field(..., description="Text after this step")


class PredictResponse(BaseModel):
    pipeline: List[PipelineStep] = Field(..., description="Text after each preprocessing step")
    tokens: Dict = Field(..., description="spaCy tokens with Porter stem, lemma, POS, stopword flag")
    representations: Dict[str, Dict] = Field(
        ..., description="Per representation: P(positive), label, vector entries, top word weights"
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
    representations: Dict
    comparison: Optional[Dict] = None
    metrics: Dict
    metrics_display: Optional[Dict] = None
    confusion_matrix: Optional[Dict] = None
    split: Optional[Dict] = None
    training: Optional[Dict] = None
    run_id: Optional[str] = None
    experiment_id: Optional[str] = None
    mlflow_url: Optional[str] = None
