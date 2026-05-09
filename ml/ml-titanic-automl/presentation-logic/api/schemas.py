"""Pydantic v2 request/response schemas for ml-titanic-automl."""
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Dict, List, Optional
try:
    from typing import Annotated, Literal
except ImportError:
    from typing_extensions import Annotated, Literal


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    request_id: Optional[str] = None


class PredictionRequest(BaseModel):
    model_config = ConfigDict(strict=True, str_strip_whitespace=True)

    pclass:   Annotated[int,   Field(ge=1, le=3,   description="Passenger class")]
    sex:      Literal["male", "female"]
    age:      Annotated[float, Field(gt=0, lt=120, description="Age in years")]
    sibsp:    Annotated[int,   Field(ge=0, le=8,   description="Siblings/spouses aboard")]
    parch:    Annotated[int,   Field(ge=0, le=6,   description="Parents/children aboard")]
    fare:     Annotated[float, Field(ge=0,         description="Ticket fare")]
    embarked: Literal["S", "C", "Q"]

    @field_validator("age", "fare", mode="before")
    @classmethod
    def round_to_two_decimals(cls, v):
        return round(float(v), 2)

    @model_validator(mode="after")
    def validate_business_rules(self):
        if self.pclass == 1 and self.fare < 5.0:
            raise ValueError("First class fare unrealistically low")
        return self


class PredictionResponse(BaseModel):
    prediction:     int
    survived:       bool
    survival_label: str
    confidence:     float
    request_id:     Optional[str] = None


class LeaderboardEntry(BaseModel):
    model:    str
    accuracy: float
    auc:      float
    f1:       float


class ModelInfoResponse(BaseModel):
    model_type:          str
    best_model:          str
    dataset:             str
    n_samples:           int
    n_features:          int
    algorithms_compared: int
    optimized_for:       str
    leaderboard:         List[Dict]
    metrics:             Dict
    metrics_display:     Optional[Dict] = None
    run_id:              Optional[str] = None
    experiment_id:       Optional[str] = None
    mlflow_url:          Optional[str] = None
