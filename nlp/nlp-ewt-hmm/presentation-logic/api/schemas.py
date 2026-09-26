"""Pydantic request/response schemas for the nlp-ewt-hmm API."""
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="API version")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=600, description="One or more English sentences")


class TokenResult(BaseModel):
    word: str
    hmm: str = Field(..., description="HMM + Viterbi tag (universal 12)")
    spacy: str = Field(..., description="spaCy tag mapped to universal 12")
    spacy_upos: str = Field(..., description="spaCy's own UPOS tag (17-tag set)")
    spacy_ptb: str = Field(..., description="spaCy's fine-grained Penn Treebank tag")
    agree: bool
    known: bool = Field(..., description="Seen in the HMM's training data")
    observation: Optional[str] = Field(None, description="The <UNK> class a rare/unseen word reads its emission from")
    emission_best: str = Field(..., description="Best tag from the emission alone, before transitions")


class SentenceResult(BaseModel):
    tokens: List[TokenResult]
    trellis: Dict = Field(..., description="Viterbi trellis: per-column shares, log scores, backpointers, best path")


class PredictResponse(BaseModel):
    tags: List[str] = Field(..., description="Trellis row order")
    sentences: List[SentenceResult]
    summary: Dict
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
    tagset: Dict
    metrics: Dict
    metrics_display: Optional[Dict] = None
    unknown_ladder: Optional[Dict] = None
    spacy_comparison: Optional[Dict] = None
    hmm_tables: Optional[Dict] = None
    confusion_matrix: Optional[Dict] = None
    split: Optional[Dict] = None
    training: Optional[Dict] = None
    run_id: Optional[str] = None
    experiment_id: Optional[str] = None
    mlflow_url: Optional[str] = None
