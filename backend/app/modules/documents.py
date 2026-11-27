from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/documents", tags=["documents"])


class Document(BaseModel):
    id: UUID
    filename: str
    format: Literal["pdf", "docx"]
    size_bytes: int = Field(ge=1)
    state: Literal["received", "extracted", "needs_review", "failed"]


@router.get("", response_model=list[Document])
def list_documents() -> list[Document]:
    return []
