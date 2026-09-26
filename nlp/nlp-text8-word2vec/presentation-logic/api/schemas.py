"""Pydantic request/response schemas for the nlp-text8-word2vec API."""
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="API version")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class NeighborsRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z][A-Za-z\-']*$", description="One word")
    topn: int = Field(10, ge=1, le=25)


class AnalogyRequest(BaseModel):
    """a − b + c, e.g. king − man + woman."""
    a: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z][A-Za-z\-']*$", description="Start word (king)")
    b: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z][A-Za-z\-']*$", description="Subtract (man)")
    c: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z][A-Za-z\-']*$", description="Add (woman)")


class SimilarityRequest(BaseModel):
    w1: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z][A-Za-z\-']*$", description="First word")
    w2: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z][A-Za-z\-']*$", description="Second word")


class MapRequest(BaseModel):
    words: List[str] = Field(..., min_length=2, max_length=30, description="Words to plot")


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
    models: Dict
    comparison: Optional[Dict] = None
    metrics: Dict
    metrics_display: Optional[Dict] = None
    confusion_matrix: Optional[Dict] = None
    split: Optional[Dict] = None
    training: Optional[Dict] = None
    run_id: Optional[str] = None
    experiment_id: Optional[str] = None
    mlflow_url: Optional[str] = None
