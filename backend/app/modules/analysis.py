from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from ..contracts import AnalysisResult

router = APIRouter(prefix="/analyses", tags=["analysis"])


class AnalysisRun(BaseModel):
    id: UUID
    document_ids: list[UUID]
    state: Literal["queued", "running", "completed", "failed"]
    results: list[AnalysisResult]


@router.get("", response_model=list[AnalysisRun])
def list_analyses() -> list[AnalysisRun]:
    return []
