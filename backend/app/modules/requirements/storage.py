import logging
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Literal

from ...contracts import Requirement
from .models import CatalogError, Package, Revision

log = logging.getLogger(__name__)


@contextmanager
def connection(path: Path, *, write: bool = False) -> Iterator[sqlite3.Connection]:
    try:
        with closing(sqlite3.connect(path)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
    except (sqlite3.Error, OSError) as exc:
        log.error("Requirements storage failure: %s", getattr(exc, "sqlite_errorname", type(exc).__name__))
        raise CatalogError(503, "Локальное хранилище требований недоступно.") from None


def initialize(path: Path) -> None:
    with connection(path, write=True) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS requirement_revisions (
                revision TEXT PRIMARY KEY NOT NULL,
                order_number TEXT NOT NULL CHECK(order_number = '117'),
                revision_date TEXT NOT NULL,
                obtained_on TEXT NOT NULL,
                source TEXT NOT NULL,
                sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
                imported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                reviewed_at TEXT,
                state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','published','archived')),
                active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0,1)),
                CHECK(active = 0 OR state = 'published'),
                CHECK(state != 'published' OR reviewed_at IS NOT NULL)
            )
        """)
        db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_active_requirement_revision
                      ON requirement_revisions(active) WHERE active = 1""")
        db.execute("""
            CREATE TABLE IF NOT EXISTS requirement_entries (
                revision TEXT NOT NULL REFERENCES requirement_revisions(revision),
                requirement_id TEXT NOT NULL,
                clause TEXT NOT NULL,
                requirement_text TEXT NOT NULL,
                ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
                PRIMARY KEY(revision, requirement_id),
                UNIQUE(revision, clause),
                UNIQUE(revision, ordinal)
            )
        """)


REVISION_SELECT = """
    SELECT r.*, (SELECT count(*) FROM requirement_entries e WHERE e.revision = r.revision)
        AS requirement_count FROM requirement_revisions r
"""


def get_revision(db: sqlite3.Connection, revision: str) -> Revision:
    row = db.execute(REVISION_SELECT + " WHERE r.revision = ?", (revision,)).fetchone()
    if row is None:
        raise CatalogError(404, "Редакция не найдена.")
    return Revision(**row)


def revisions(path: Path) -> list[Revision]:
    with connection(path) as db:
        return [Revision(**row) for row in db.execute(REVISION_SELECT + " ORDER BY revision_date DESC, revision")]


def active_revision(path: Path) -> Revision | None:
    with connection(path) as db:
        row = db.execute(REVISION_SELECT + " WHERE active = 1").fetchone()
        return Revision(**row) if row else None


def active_count(path: Path) -> int:
    with connection(path) as db:
        return db.execute("""SELECT count(*) FROM requirement_entries JOIN requirement_revisions
                             USING(revision) WHERE active = 1""").fetchone()[0]


def read_requirements(path: Path, revision: str | None = None) -> list[Requirement]:
    with connection(path) as db:
        if revision is None:
            where, params = "active = 1", ()
        else:
            get_revision(db, revision)
            where, params = "revision = ?", (revision,)
        rows = db.execute("""
            SELECT requirement_id, requirement_text, order_number, revision, clause
            FROM requirement_entries JOIN requirement_revisions USING(revision) WHERE
        """ + where + " ORDER BY ordinal", params)
        return [Requirement(requirement_id=row["requirement_id"], requirement_text=row["requirement_text"],
                            source_reference={key: row[key] for key in ("order_number", "revision", "clause")})
                for row in rows]


def save(path: Path, package: Package, digest: str) -> tuple[Revision, bool]:
    with connection(path, write=True) as db:
        row = db.execute("SELECT sha256 FROM requirement_revisions WHERE revision = ?", (package.revision,)).fetchone()
        if row:
            if row["sha256"] != digest:
                raise CatalogError(409, "Эта редакция уже существует с другой контрольной суммой пакета.")
            return get_revision(db, package.revision), False
        db.execute("""INSERT INTO requirement_revisions
                   (revision, order_number, revision_date, obtained_on, source, sha256)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                   (package.revision, package.order_number, package.revision_date.isoformat(),
                    package.obtained_on.isoformat(), package.source, digest))
        db.executemany("""INSERT INTO requirement_entries
                       (revision, requirement_id, clause, requirement_text, ordinal) VALUES (?, ?, ?, ?, ?)""",
                       ((package.revision, item.requirement_id, item.clause, item.requirement_text, i)
                        for i, item in enumerate(package.requirements)))
        return get_revision(db, package.revision), True


Operation = Literal["publish", "activate", "archive", "deactivate"]


def delete_archived(path: Path, revision: str) -> None:
    with connection(path, write=True) as db:
        current = get_revision(db, revision)
        if current.state != "archived" or current.active:
            raise CatalogError(409, "Удалить можно только архивную редакцию.")
        db.execute("DELETE FROM requirement_entries WHERE revision = ?", (revision,))
        db.execute("DELETE FROM requirement_revisions WHERE revision = ?", (revision,))


def transition(path: Path, revision: str, operation: Operation) -> Revision:
    with connection(path, write=True) as db:
        current = get_revision(db, revision)
        if operation == "publish":
            if current.state != "draft":
                raise CatalogError(409, "Опубликовать можно только черновик.")
            db.execute("""UPDATE requirement_revisions SET state='published',
                       reviewed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE revision=?""", (revision,))
        elif operation == "activate":
            if current.state != "published":
                raise CatalogError(409, "Выбрать активной можно только опубликованную редакцию.")
            db.execute("UPDATE requirement_revisions SET active=0 WHERE active=1")
            db.execute("UPDATE requirement_revisions SET active=1 WHERE revision=?", (revision,))
        elif operation == "archive":
            if current.active:
                raise CatalogError(409, "Сначала снимите редакцию с использования или выберите другую.")
            db.execute("UPDATE requirement_revisions SET state='archived' WHERE revision=?", (revision,))
        elif operation == "deactivate":
            db.execute("UPDATE requirement_revisions SET active=0 WHERE revision=?", (revision,))
        return get_revision(db, revision)
