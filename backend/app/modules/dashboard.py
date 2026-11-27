from fastapi import APIRouter
from pydantic import BaseModel, Field

from . import analysis, documents, reports, requirements

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummary(BaseModel):
    documents: int = Field(ge=0)
    requirements: int = Field(ge=0)
    analyses: int = Field(ge=0)
    reports: int = Field(ge=0)


@router.get("/summary", response_model=DashboardSummary)
def summary() -> DashboardSummary:
    return DashboardSummary(
        documents=len(documents.list_documents()),
        requirements=len(requirements.list_requirements()),
        analyses=len(analysis.list_analyses()),
        reports=len(reports.list_reports()),
    )
