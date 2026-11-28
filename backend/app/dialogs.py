import sqlite3
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import Header

from .db import transaction

LEGACY_DIALOG = UUID(int=0)
DialogId = Annotated[UUID, Header(alias="X-Dialog-Id")]


class DialogDeleted(Exception):
    pass


def initialize(path: Path) -> None:
    with transaction(path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS deleted_dialogs (id TEXT PRIMARY KEY)")


def ensure_open(db: sqlite3.Connection, dialog_id: UUID) -> None:
    if db.execute("SELECT 1 FROM deleted_dialogs WHERE id = ?", (str(dialog_id),)).fetchone():
        raise DialogDeleted("Диалог удалён. Откройте новый чат.")


def delete(path: Path, dialog_id: UUID) -> None:
    key = (str(dialog_id),)
    with transaction(path) as db:
        db.execute("BEGIN IMMEDIATE")
        if dialog_id != LEGACY_DIALOG:
            db.execute("INSERT OR IGNORE INTO deleted_dialogs (id) VALUES (?)", key)
        db.execute("DELETE FROM analysis_reports WHERE analysis_id IN (SELECT id FROM analysis_runs WHERE dialog_id = ?)", key)
        db.execute("DELETE FROM analysis_runs WHERE dialog_id = ?", key)
        db.execute("DELETE FROM documents WHERE dialog_id = ?", key)
