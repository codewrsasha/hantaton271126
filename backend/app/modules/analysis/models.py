from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator

from ...contracts import AnalysisResult, ExpertReview
from ..documents.models import Document

RevisionKey = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")]


class StartAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_ids: list[UUID] = Field(min_length=1, max_length=16)
    revision: RevisionKey | None = None

    @field_validator("document_ids")
    @classmethod
    def distinct_documents(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("duplicate documents")
        return value


class ReviewUpdate(ExpertReview):
    model_config = ConfigDict(extra="forbid")
    comment: str = Field(min_length=1, max_length=4000)


class AnalysisDocument(Document):
    fragment_count: int = Field(ge=0)


class AnalysisRun(BaseModel):
    id: UUID
    document_ids: list[UUID]
    state: Literal["queued", "running", "completed", "failed"]
    results: list[AnalysisResult]
    revision: str
    source: str
    revision_sha256: str
    revision_date: date
    obtained_on: date
    created_at: AwareDatetime
    documents: list[AnalysisDocument]
    error: str | None = None
