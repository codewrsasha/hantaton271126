from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class RegulatorySource(BaseModel):
    order_number: Literal["117"]
    revision: str = Field(min_length=1)
    clause: str = Field(min_length=1)


class Requirement(BaseModel):
    requirement_id: str = Field(min_length=1)
    requirement_text: str = Field(min_length=1)
    source_reference: RegulatorySource


class PdfLocation(BaseModel):
    kind: Literal["pdf_page"]
    page: int = Field(ge=1)


class DocxLocation(BaseModel):
    kind: Literal["docx_section"]
    section: str = Field(min_length=1)


class UnknownLocation(BaseModel):
    kind: Literal["unknown"]


Location = Annotated[
    PdfLocation | DocxLocation | UnknownLocation, Field(discriminator="kind")
]


class Evidence(BaseModel):
    document_id: UUID
    filename: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    location: Location
    relation: Literal["supports", "contradicts", "context"]


ComplianceStatus = Literal[
    "соответствует",
    "частично соответствует",
    "не соответствует",
    "недостаточно данных",
    "требуется проверка",
]


class ExpertReview(BaseModel):
    comment: str = Field(min_length=1)
    corrected_status: ComplianceStatus | None = None


class AnalysisResult(Requirement):
    status: ComplianceStatus
    evidence: list[Evidence]
    explanation: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    review: ExpertReview | None = None

    @model_validator(mode="after")
    def validate_evidence(self) -> "AnalysisResult":
        status = self.review.corrected_status if self.review else None
        for current in (self.status, status):
            if current == "соответствует" and not any(
                item.relation == "supports" and item.location.kind != "unknown"
                for item in self.evidence
            ):
                raise ValueError("Compliance requires traceable supporting evidence")
            if current == "не соответствует" and not any(
                item.relation == "contradicts" for item in self.evidence
            ):
                raise ValueError("Noncompliance requires contradictory evidence")
        return self
