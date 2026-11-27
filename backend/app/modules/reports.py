from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/reports", tags=["reports"])


class Report(BaseModel):
    id: UUID
    analysis_id: UUID
    filename: str


@router.get("", response_model=list[Report])
def list_reports() -> list[Report]:
    return []
