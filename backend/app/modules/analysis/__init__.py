from datetime import datetime, timezone
from threading import Lock
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from ...contracts import AnalysisResult
from ...local_api import ErrorResponse, LocalActionRoute, local_action
from ..documents import storage as documents
from ..requirements import storage as catalog
from . import matching, storage
from .models import AnalysisDocument, AnalysisRun, ReviewUpdate, StartAnalysis
from .storage import count as count_analyses
from .storage import fetch as get_run
from .storage import initialize

router = APIRouter(
    prefix="/analyses", tags=["analysis"], route_class=LocalActionRoute,
    responses={code: {"model": ErrorResponse} for code in (403, 404, 409, 422, 429, 503)},
)
analysis_slot = Lock()


@router.get("")
def list_analyses(request: Request) -> list[AnalysisRun]:
    return storage.list_runs(request.app.state.database_path)


@router.get("/{analysis_id}")
def analysis_details(request: Request, analysis_id: UUID) -> AnalysisRun:
    run = get_run(request.app.state.database_path, analysis_id)
    if run is None:
        raise HTTPException(404, "Проверка не найдена.")
    return run


@router.post("", status_code=201, dependencies=[Depends(local_action)])
def start_analysis(request: Request, data: StartAnalysis) -> AnalysisRun:
    path = request.app.state.database_path
    if not analysis_slot.acquire(blocking=False):
        raise HTTPException(429, "Уже выполняется проверка. Повторите попытку после её завершения.")
    try:
        active = catalog.active_revision(path)
        if active is None or active.state != "published":
            raise HTTPException(409, "В каталоге нет активной опубликованной редакции.")
        if data.revision is not None and active.revision != data.revision:
            raise HTTPException(409, "Активная редакция изменилась. Обновите страницу перед запуском.")
        requirements = catalog.read_requirements(path, active.revision)
        if not requirements:
            raise HTTPException(409, "В активной редакции нет требований.")

        selected = []
        sources = []
        for document_id in data.document_ids:
            document = documents.get_document(path, document_id)
            if document is None:
                raise HTTPException(404, "Один из выбранных документов не найден.")
            fragments = documents.read_fragments(path, document_id)
            selected.append(AnalysisDocument(**document.model_dump(), fragment_count=len(fragments)))
            sources.extend(matching.MatchSource(document, fragment) for fragment in fragments)

        run = AnalysisRun(
            id=uuid4(), document_ids=data.document_ids, state="running", results=[],
            revision=active.revision, source=active.source, revision_sha256=active.sha256,
            revision_date=active.revision_date, obtained_on=active.obtained_on,
            created_at=datetime.now(timezone.utc), documents=selected,
        )
        storage.insert(path, run)
        try:
            run.results = matching.evaluate(requirements, selected, sources)
            run.state = "completed"
        except Exception:
            run.state = "failed"
            run.error = "Не удалось завершить предварительный анализ. Повторите проверку."
        storage.finish(path, run)
        return run
    finally:
        analysis_slot.release()


@router.put("/{analysis_id}/results/{requirement_id}/review", dependencies=[Depends(local_action)])
def review_result(request: Request, analysis_id: UUID, requirement_id: str, review: ReviewUpdate) -> AnalysisResult:
    try:
        return storage.save_review(request.app.state.database_path, analysis_id, requirement_id, review)
    except storage.ReviewError as error:
        raise HTTPException(error.status, str(error)) from None
