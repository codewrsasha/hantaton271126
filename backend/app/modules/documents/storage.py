import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from uuid import UUID

from pydantic import TypeAdapter

from ...contracts import Location
from .models import Document, DocumentIssue, Fragment

location_adapter = TypeAdapter(Location)


@contextmanager
def connection(path: Path) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        yield db


def initialize(path: Path) -> None:
    with connection(path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                storage_name TEXT NOT NULL UNIQUE,
                format TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                state TEXT NOT NULL,
                issue_json TEXT,
                original BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS document_fragments (
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                ordinal INTEGER NOT NULL,
                text TEXT NOT NULL,
                location_json TEXT NOT NULL,
                PRIMARY KEY (document_id, ordinal)
            );
        """)


def save(path: Path, document: Document, original: bytes, fragments: list[Fragment]) -> None:
    with connection(path) as db:
        db.execute(
            """
            INSERT INTO documents
                (id, filename, storage_name, format, size_bytes, state, issue_json, original)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(document.id), document.filename, f"{document.id.hex}.{document.format}",
                document.format, document.size_bytes, document.state,
                document.issue.model_dump_json() if document.issue else None, original,
            ),
        )
        db.executemany(
            "INSERT INTO document_fragments VALUES (?, ?, ?, ?)",
            (
                (str(document.id), ordinal, item.text, location_adapter.dump_json(item.location).decode())
                for ordinal, item in enumerate(fragments, start=1)
            ),
        )


def _document(row) -> Document:
    id_, filename, format_, size, state, issue = row
    return Document(
        id=id_, filename=filename, format=format_, size_bytes=size, state=state,
        issue=DocumentIssue.model_validate_json(issue) if issue is not None else None,
    )


def get_document(path: Path, document_id: UUID) -> Document | None:
    """Read metadata for one document without loading the original BLOB."""
    with connection(path) as db:
        row = db.execute(
            "SELECT id, filename, format, size_bytes, state, issue_json FROM documents WHERE id = ?",
            (str(document_id),),
        ).fetchone()
    return _document(row) if row is not None else None


def list_documents(path: Path) -> list[Document]:
    with connection(path) as db:
        rows = db.execute(
            "SELECT id, filename, format, size_bytes, state, issue_json FROM documents ORDER BY rowid DESC"
        ).fetchall()

    return [_document(row) for row in rows]


def count_documents(path: Path) -> int:
    with connection(path) as db:
        return db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]


def read_fragments(path: Path, document_id: UUID) -> list[Fragment]:
    """Read fragments for a known document in source order, including partial results."""
    with connection(path) as db:
        rows = db.execute(
            "SELECT text, location_json FROM document_fragments WHERE document_id = ? ORDER BY ordinal",
            (str(document_id),),
        ).fetchall()
    return [Fragment(text, location_adapter.validate_json(location)) for text, location in rows]
