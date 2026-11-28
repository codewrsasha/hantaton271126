import asyncio
import sqlite3
import unicodedata
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from . import docx, pdf, storage
from .models import Document, ErrorResponse, RejectedUpload, UploadLimits
from .upload import receive_file

router = APIRouter(prefix="/documents", tags=["documents"])


def initialize(path: Path) -> None:
    storage.initialize(path)


def count_documents(path: Path) -> int:
    return storage.count_documents(path)


def display_filename(filename: str, format_: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    safe = "".join(char for char in basename if unicodedata.category(char)[0] != "C").strip()
    return safe[:255] if safe and safe not in {".", ".."} else f"document.{format_}"


def ingest(path: Path, filename: str, content: bytes) -> Document:
    if content.startswith(b"%PDF-"):
        result = pdf.extract(content)
    elif content.startswith(b"PK\x03\x04"):
        result = docx.extract(content)
    else:
        raise RejectedUpload(415, "Поддерживаются только файлы PDF и DOCX. Формат определяется по содержимому.")

    document = Document(
        id=uuid4(), filename=display_filename(filename, result.format), format=result.format,
        size_bytes=len(content), state=result.state, issue=result.issue,
    )
    storage.save(path, document, content, result.fragments)
    return document


@router.get("", responses={503: {"model": ErrorResponse}})
def list_documents(request: Request) -> list[Document]:
    try:
        return storage.list_documents(request.app.state.database_path)
    except sqlite3.Error as error:
        raise HTTPException(503, "Не удалось прочитать список документов. Проверьте доступность локального хранилища.") from error


@router.get("/limits")
def upload_limits(request: Request) -> UploadLimits:
    return UploadLimits(max_size_bytes=request.app.state.document_max_bytes)


@router.get("/{document_id}/fragments")
def document_fragments(document_id: UUID, request: Request):
    try:
        if not any(doc.id == document_id for doc in storage.list_documents(request.app.state.database_path)):
            raise HTTPException(404, "Документ не найден.")
        return storage.read_fragments(request.app.state.database_path, document_id)
    except sqlite3.Error as error:
        raise HTTPException(503, "Не удалось прочитать документ.") from error


@router.post(
    "", status_code=201, response_model=Document,
    responses={code: {"model": ErrorResponse} for code in (400, 408, 413, 415, 422, 429, 503)},
    openapi_extra={"requestBody": {"required": True, "content": {"multipart/form-data": {
        "schema": {"type": "object", "required": ["file"], "additionalProperties": False,
                   "properties": {"file": {"type": "string", "format": "binary"}}},
    }}}},
)
async def upload_document(request: Request) -> Document:
    slots = request.app.state.document_upload_slots
    if slots.locked():
        raise HTTPException(429, "Сервер обрабатывает другие загрузки. Повторите попытку позже.")

    async with slots:
        try:
            async with asyncio.timeout(30):
                filename, content = await receive_file(request, request.app.state.document_max_bytes)
            return await run_in_threadpool(ingest, request.app.state.database_path, filename, content)
        except TimeoutError as error:
            raise HTTPException(408, "Истекло время приёма файла. Повторите загрузку.") from error
        except RejectedUpload as error:
            raise HTTPException(error.status_code, str(error)) from error
        except (sqlite3.Error, OSError) as error:
            raise HTTPException(503, "Не удалось сохранить документ. Проверьте доступность локального хранилища.") from error
