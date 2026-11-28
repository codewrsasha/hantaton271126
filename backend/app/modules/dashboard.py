import sqlite3

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import analysis, documents, reports, requirements

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummary(BaseModel):
    documents: int = Field(ge=0)
    requirements: int = Field(ge=0)
    analyses: int = Field(ge=0)
    reports: int = Field(ge=0)


@router.get("/summary", response_model=DashboardSummary)
def summary(request: Request) -> DashboardSummary:
    try:
        document_count = documents.count_documents(request.app.state.database_path)
    except sqlite3.Error as error:
        raise HTTPException(503, "Не удалось прочитать сводку из локального хранилища.") from error
    return DashboardSummary(
        documents=document_count,
        requirements=requirements.catalog().revision.requirement_count,
        analyses=analysis.count_analyses(request.app.state.database_path),
        reports=reports.count_reports(request.app.state.database_path),
    )
