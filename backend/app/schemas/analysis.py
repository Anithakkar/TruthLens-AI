from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from uuid import UUID

from app.schemas.submission import NewsSubmissionCreate


class NewsAnalysisRequest(NewsSubmissionCreate):
    submission_id: UUID | None = None


class ModelSignal(BaseModel):
    term: str
    contribution: float


class ModelResult(BaseModel):
    status: Literal["available", "not_trained", "unavailable"]
    benchmark_label: str | None = None
    label_description: str | None = None
    model_score: float | None = Field(default=None, ge=0, le=1)
    top_signals: list[ModelSignal] = Field(default_factory=list)
    counter_signals: list[ModelSignal] = Field(default_factory=list)
    explanation: str | None = None
    message: str | None = None


class ModelComparison(BaseModel):
    traditional: ModelResult
    transformer: ModelResult


class FactCheckItem(BaseModel):
    claim: str
    publisher: str
    title: str
    rating: str
    url: str
    review_date: str


class FactCheckResults(BaseModel):
    status: Literal["not_configured", "unavailable", "no_matches", "matches"]
    message: str
    items: list[FactCheckItem]


class NewsAnalysisResponse(BaseModel):
    submission_id: UUID | None
    benchmark_label: str
    label_description: str
    model_score: float = Field(ge=0, le=1)
    top_signals: list[ModelSignal]
    counter_signals: list[ModelSignal]
    explanation: str
    model_comparison: ModelComparison | None = None
    fact_checks: FactCheckResults
    notice: str
