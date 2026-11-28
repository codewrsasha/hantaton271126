import json
import sqlite3
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from ...contracts import AnalysisResult, ExpertReview
from ...db import transaction
from ...dialogs import LEGACY_DIALOG, ensure_open
from .models import AnalysisRun

INTERRUPTED = "Работа приложения прервалась. Запустите проверку заново."


class ReviewError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def initialize(path: Path) -> None:
    with transaction(path) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS analysis_runs (
                id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                snapshot TEXT NOT NULL,
                reviews TEXT NOT NULL DEFAULT '{}',
                error TEXT
            )
        """)
        db.execute("BEGIN IMMEDIATE")
        if not any(column[1] == "dialog_id" for column in db.execute("PRAGMA table_info(analysis_runs)")):
            db.execute(f"ALTER TABLE analysis_runs ADD COLUMN dialog_id TEXT NOT NULL DEFAULT '{LEGACY_DIALOG}'")
        db.execute("CREATE INDEX IF NOT EXISTS analysis_dialog_idx ON analysis_runs (dialog_id)")
        db.execute(
            "UPDATE analysis_runs SET state = 'failed', error = ? WHERE state IN ('running', 'queued')",
            (INTERRUPTED,),
        )


def insert(path: Path, run: AnalysisRun, dialog_id: UUID = LEGACY_DIALOG) -> None:
    with transaction(path) as db:
        db.execute("BEGIN IMMEDIATE")
        ensure_open(db, dialog_id)
        db.execute("INSERT INTO analysis_runs (id, state, snapshot, dialog_id) VALUES (?, ?, ?, ?)",
                   (str(run.id), run.state, run.model_dump_json(), str(dialog_id)))


def finish(path: Path, run: AnalysisRun) -> None:
    with transaction(path) as db:
        updated = db.execute(
            "UPDATE analysis_runs SET state = ?, snapshot = ?, error = ? WHERE id = ? AND state = 'running'",
            (run.state, run.model_dump_json(), run.error, str(run.id)),
        )
        if updated.rowcount != 1:
            raise sqlite3.OperationalError("Analysis run was interrupted")


def read_run(row) -> AnalysisRun:
    state, snapshot, review_json, error = row
    run = AnalysisRun.model_validate_json(snapshot)
    reviews = json.loads(review_json)
    if reviews:
        run.results = [
            with_review(result, ExpertReview.model_validate(reviews[result.requirement_id]))
            if result.requirement_id in reviews else result
            for result in run.results
        ]
    run.state = state
    run.error = error
    return run


def with_review(result: AnalysisResult, review: ExpertReview) -> AnalysisResult:
    return AnalysisResult.model_validate({**result.model_dump(), "review": review})


SELECT = "SELECT state, snapshot, reviews, error FROM analysis_runs"


def fetch(path: Path, analysis_id: UUID, dialog_id: UUID = LEGACY_DIALOG) -> AnalysisRun | None:
    with transaction(path) as db:
        row = db.execute(SELECT + " WHERE id = ? AND dialog_id = ?", (str(analysis_id), str(dialog_id))).fetchone()
    return read_run(row) if row else None


def list_runs(path: Path, dialog_id: UUID = LEGACY_DIALOG) -> list[AnalysisRun]:
    with transaction(path) as db:
        rows = db.execute(SELECT + " WHERE dialog_id = ? ORDER BY rowid DESC", (str(dialog_id),)).fetchall()
    return [read_run(row) for row in rows]


def count(path: Path, dialog_id: UUID = LEGACY_DIALOG) -> int:
    with transaction(path) as db:
        return db.execute("SELECT COUNT(*) FROM analysis_runs WHERE dialog_id = ?", (str(dialog_id),)).fetchone()[0]


def save_review(
    path: Path, analysis_id: UUID, requirement_id: str, review: ExpertReview, dialog_id: UUID = LEGACY_DIALOG,
) -> AnalysisResult:
    with transaction(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(SELECT + " WHERE id = ? AND dialog_id = ?", (str(analysis_id), str(dialog_id))).fetchone()
        if not row:
            raise ReviewError(404, "Проверка не найдена.")
        state, snapshot, review_json, _ = row
        if state != "completed":
            raise ReviewError(409, "Экспертная правка доступна после завершения проверки.")
        original = AnalysisRun.model_validate_json(snapshot)
        result = next((item for item in original.results if item.requirement_id == requirement_id), None)
        if result is None:
            raise ReviewError(404, "Требование не найдено в этой проверке.")
        try:
            updated = with_review(result, review)
        except ValidationError:
            raise ReviewError(
                422, "Для выбранного статуса отметьте подходящую цитату. "
                "Подтверждение требует известного местоположения."
            ) from None

        reviews = json.loads(review_json)
        reviews[requirement_id] = review.model_dump(mode="json")
        db.execute("UPDATE analysis_runs SET reviews = ? WHERE id = ?",
                   (json.dumps(reviews, ensure_ascii=False), str(analysis_id)))
        return updated
