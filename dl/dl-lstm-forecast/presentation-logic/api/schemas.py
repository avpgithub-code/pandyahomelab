"""Pydantic request/response schemas for dl-lstm-forecast API."""
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="API version")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class ForecastRequest(BaseModel):
    anchor_date: str = Field(
        ...,
        description="Anchor date (YYYY-MM-DD) — last observed day before the forecast begins",
    )
    horizon: Optional[int] = Field(
        None,
        ge=1,
        le=60,
        description="Number of days ahead to forecast (default 14)",
    )
    n_samples: Optional[int] = Field(
        None,
        ge=1,
        le=200,
        description="MC-Dropout sample count per autoregressive step (default 30)",
    )

    @field_validator("anchor_date")
    @classmethod
    def validate_anchor_date(cls, v: str) -> str:
        # Cheap sanity — full validity is checked downstream by the loader.
        if len(v) != 10 or v[4] != "-" or v[7] != "-":
            raise ValueError("anchor_date must be in YYYY-MM-DD format")
        return v


class ForecastPoint(BaseModel):
    day_offset: int = Field(..., description="Days after anchor (1..horizon)")
    date: str = Field(..., description="Forecasted date (YYYY-MM-DD)")
    mean: int = Field(..., description="Mean forecast (rides/day)")
    lower: int = Field(..., description="Lower bound of 95% confidence band (mean − 2σ)")
    upper: int = Field(..., description="Upper bound of 95% confidence band (mean + 2σ)")
    actual: Optional[int] = Field(
        None,
        description="Actual ride count if this date is in the historical record; null otherwise",
    )


class ForecastResponse(BaseModel):
    anchor_date: str = Field(..., description="Resolved anchor date (YYYY-MM-DD)")
    horizon: int = Field(..., description="Forecast horizon (days)")
    window_size: int = Field(..., description="Input window length (days)")
    points: List[ForecastPoint]
    request_id: Optional[str] = None


class HistoryResponse(BaseModel):
    dates: List[str] = Field(..., description="All historical dates (YYYY-MM-DD)")
    trips: List[int] = Field(..., description="Daily ride counts aligned with `dates`")
    min_anchor: str = Field(
        ...,
        description="Earliest date that has window_size preceding days — use to clamp the date picker",
    )
    max_anchor: str = Field(..., description="Latest historical date")
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
    metrics: Dict
    metrics_display: Optional[Dict] = None
    split: Optional[Dict] = None
    run_id: Optional[str] = None
    experiment_id: Optional[str] = None
    mlflow_url: Optional[str] = None
