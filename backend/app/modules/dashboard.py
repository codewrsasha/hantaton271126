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
        path = request.app.state.database_path
        return DashboardSummary(
            documents=documents.count_documents(path),
            requirements=requirements.storage.active_count(path),
            analyses=analysis.count_analyses(path),
            reports=reports.count_reports(path),
        )
    except sqlite3.Error as error:
        raise HTTPException(503, "Не удалось прочитать сводку из локального хранилища.") from error
