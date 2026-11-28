from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ...contracts import Location

DocumentFormat = Literal["pdf", "docx"]
DocumentState = Literal["received", "extracted", "needs_review", "failed"]
IssueCode = Literal["no_text", "partial_extraction", "extraction_failed", "unknown_location"]


class DocumentIssue(BaseModel):
    code: IssueCode
    message: str


class Document(BaseModel):
    id: UUID
    filename: str
    format: DocumentFormat
    size_bytes: int = Field(ge=1)
    state: DocumentState
    issue: DocumentIssue | None = None


class UploadLimits(BaseModel):
    max_size_bytes: int = Field(ge=1)


class ErrorResponse(BaseModel):
    detail: str


@dataclass(frozen=True)
class Fragment:
    text: str
    location: Location


@dataclass
class Extraction:
    format: DocumentFormat
    fragments: list[Fragment] = field(default_factory=list)
    issue: DocumentIssue | None = None

    @property
    def state(self) -> DocumentState:
        if self.issue is None:
            return "extracted"
        return "failed" if self.issue.code == "extraction_failed" else "needs_review"


class RejectedUpload(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
