from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


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


EvidenceRelation = Literal["supports", "contradicts", "context"]


class Evidence(BaseModel):
    document_id: UUID
    filename: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    location: Location
    relation: EvidenceRelation


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
    evidence_relations: dict[int, EvidenceRelation] = Field(default_factory=dict)

    @field_validator("comment", mode="before")
    @classmethod
    def trim_comment(cls, value):
        return value.strip() if isinstance(value, str) else value


class AnalysisResult(Requirement):
    status: ComplianceStatus
    evidence: list[Evidence]
    explanation: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    review: ExpertReview | None = None

    @model_validator(mode="after")
    def validate_evidence(self) -> "AnalysisResult":
        self.check_status(self.status, [item.relation for item in self.evidence])
        if self.review:
            assignments = self.review.evidence_relations
            if any(not 0 <= index < len(self.evidence) for index in assignments):
                raise ValueError("Review references unknown evidence")
            if self.review.corrected_status:
                corrected = self.review.corrected_status
                self.check_status("соответствует" if corrected == "частично соответствует" else corrected, [
                    assignments.get(index, item.relation)
                    for index, item in enumerate(self.evidence)
                ])
        return self

    def check_status(self, status: ComplianceStatus, relations: list[EvidenceRelation]) -> None:
        if status == "соответствует" and not any(
            relation == "supports" and item.location.kind != "unknown"
            for item, relation in zip(self.evidence, relations)
        ):
            raise ValueError("Compliance requires traceable supporting evidence")
        if status == "не соответствует" and "contradicts" not in relations:
            raise ValueError("Noncompliance requires contradictory evidence")
