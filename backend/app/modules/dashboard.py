import sqlite3

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..dialogs import DialogId, LEGACY_DIALOG
from . import analysis, documents, reports, requirements

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummary(BaseModel):
    documents: int = Field(ge=0)
    requirements: int = Field(ge=0)
    analyses: int = Field(ge=0)
    reports: int = Field(ge=0)


@router.get("/summary", response_model=DashboardSummary)
def summary(request: Request, dialog_id: DialogId = LEGACY_DIALOG) -> DashboardSummary:
    path = request.app.state.database_path
    try:
        return DashboardSummary(
            documents=documents.count_documents(path, dialog_id),
            requirements=requirements.catalog().revision.requirement_count,
            analyses=analysis.count_analyses(path, dialog_id),
            reports=reports.count_reports(path, dialog_id),
        )
    except sqlite3.Error as error:
        raise HTTPException(503, "Не удалось прочитать сводку из локального хранилища.") from error
