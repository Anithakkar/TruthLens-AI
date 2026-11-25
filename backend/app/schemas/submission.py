from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


class NewsSubmissionCreate(BaseModel):
    headline: str = Field(min_length=5, max_length=300)
    article_text: str = Field(min_length=40, max_length=20_000)
    source_name: str | None = Field(default=None, max_length=200)
    source_url: HttpUrl | None = None

    @field_validator("headline", "article_text", "source_name", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class NewsSubmissionResponse(BaseModel):
    id: UUID
    status: Literal["received"]
    created_at: datetime


class NewsSubmissionRecord(BaseModel):
    id: UUID
    headline: str
    article_text: str
    source_name: str | None
    source_url: str | None
    status: str
    created_at: datetime
    analysis_result: dict[str, object] | None = None
