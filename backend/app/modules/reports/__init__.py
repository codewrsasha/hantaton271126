from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict

from ...db import transaction
from ...dialogs import DialogId, LEGACY_DIALOG
from ...local_api import ErrorResponse, LocalActionRoute, local_action
from ..analysis import get_run
from .render import CSP, render

router = APIRouter(
    prefix="/reports", tags=["reports"], route_class=LocalActionRoute,
    responses={code: {"model": ErrorResponse} for code in (403, 404, 409, 422, 503)},
)


class Report(BaseModel):
    id: UUID
    analysis_id: UUID
    filename: str


class CreateReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_id: UUID


def initialize(path: Path) -> None:
    with transaction(path) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS analysis_reports (
                id TEXT PRIMARY KEY,
                analysis_id TEXT NOT NULL REFERENCES analysis_runs(id),
                html TEXT NOT NULL
            )
        """)


REPORTS = "FROM analysis_reports AS reports JOIN analysis_runs AS runs ON runs.id = reports.analysis_id"


def count_reports(path: Path, dialog_id: UUID = LEGACY_DIALOG) -> int:
    with transaction(path) as db:
        return db.execute(f"SELECT COUNT(*) {REPORTS} WHERE runs.dialog_id = ?", (str(dialog_id),)).fetchone()[0]


def report_filename(report_id: UUID) -> str:
    return f"report-{report_id}.html"


@router.get("")
def list_reports(request: Request, dialog_id: DialogId = LEGACY_DIALOG) -> list[Report]:
    with transaction(request.app.state.database_path) as db:
        rows = db.execute(
            f"SELECT reports.id, analysis_id {REPORTS} WHERE runs.dialog_id = ? ORDER BY reports.rowid DESC",
            (str(dialog_id),),
        ).fetchall()
    return [Report(id=id_, analysis_id=analysis_id, filename=report_filename(UUID(id_))) for id_, analysis_id in rows]


@router.post("", status_code=201, dependencies=[Depends(local_action)])
def create_report(request: Request, data: CreateReport, dialog_id: DialogId = LEGACY_DIALOG) -> Report:
    path = request.app.state.database_path
    run = get_run(path, data.analysis_id, dialog_id)
    if run is None:
        raise HTTPException(404, "Проверка не найдена.")
    if run.state != "completed":
        raise HTTPException(409, "Отчёт доступен после завершения проверки.")

    hostname = request.url.hostname
    authority = f"[{hostname}]" if hostname == "::1" else hostname
    if request.url.port is not None:
        authority += f":{request.url.port}"
    scheme = "https" if request.url.scheme == "https" else "http"
    html = render(run, f"{scheme}://{authority}")
    identifier = uuid4()
    with transaction(path) as db:
        inserted = db.execute(
            """INSERT INTO analysis_reports (id, analysis_id, html)
               SELECT ?, id, ? FROM analysis_runs WHERE id = ? AND dialog_id = ?""",
            (str(identifier), html, str(run.id), str(dialog_id)),
        )
        if inserted.rowcount == 0:
            raise HTTPException(404, "Проверка не найдена.")
    return Report(id=identifier, analysis_id=run.id, filename=report_filename(identifier))


@router.get("/{report_id}/download", response_class=Response,
            responses={200: {"content": {"text/html": {"schema": {"type": "string"}}}}})
def download_report(request: Request, report_id: UUID, dialog_id: DialogId = LEGACY_DIALOG) -> Response:
    with transaction(request.app.state.database_path) as db:
        row = db.execute(
            f"SELECT html {REPORTS} WHERE reports.id = ? AND runs.dialog_id = ?", (str(report_id), str(dialog_id)),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Отчёт не найден.")
    return Response(row[0], media_type="text/html", headers={
        "Content-Disposition": f'attachment; filename="{report_filename(report_id)}"',
        "Content-Security-Policy": CSP,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    })
