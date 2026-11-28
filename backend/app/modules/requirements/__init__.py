import asyncio
from hashlib import sha256
from ipaddress import ip_address

from fastapi import APIRouter, Depends, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect
from starlette.responses import JSONResponse

from ...contracts import Requirement
from ..documents.models import RejectedUpload
from ..documents.upload import receive_file
from . import storage
from .conversion import Conversion, convert
from .models import MAX_BYTES, CatalogError, ErrorResponse, Package, Revision, parse_package
from .storage import initialize


def catalog_error_response(request: Request, error: CatalogError) -> JSONResponse:
    return JSONResponse(status_code=error.status, content={"detail": str(error)})


def local_write(request: Request) -> None:
    try:
        local = request.client is not None and ip_address(request.client.host).is_loopback
    except ValueError:
        local = False
    if (not local or request.url.hostname not in {"localhost", "127.0.0.1", "::1"}
            or request.headers.get("x-catalog-action") != "1"):
        raise CatalogError(403, "Изменение каталога разрешено только через локальный интерфейс.")


errors = {code: {"model": ErrorResponse} for code in (400, 403, 404, 408, 409, 413, 415, 422, 429, 503)}
router = APIRouter(prefix="/requirements", tags=["requirements"], responses=errors)


@router.get("")
def list_requirements(request: Request) -> list[Requirement]:
    return storage.read_requirements(request.app.state.database_path)


@router.get("/revisions")
def list_revisions(request: Request) -> list[Revision]:
    return storage.revisions(request.app.state.database_path)


@router.get("/active")
def active_revision(request: Request) -> Revision | None:
    return storage.active_revision(request.app.state.database_path)


@router.get("/revisions/{revision}/requirements")
def revision_requirements(request: Request, revision: str) -> list[Requirement]:
    return storage.read_requirements(request.app.state.database_path, revision)


def package_schema() -> dict:
    # The body is streamed to enforce the byte limit before decoding.
    schema = Package.model_json_schema()
    schema["properties"]["requirements"]["items"] = schema.pop("$defs")["Entry"]
    return schema


@router.post("/revisions", dependencies=[Depends(local_write)], status_code=201,
             responses={200: {"model": Revision}},
             openapi_extra={"requestBody": {"required": True, "content": {
                 "application/json": {"schema": package_schema()}
             }}})
async def import_revision(request: Request, response: Response) -> Revision:
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise CatalogError(415, "Передайте JSON-пакет с типом application/json.")
    body = bytearray()
    try:
        async with asyncio.timeout(30):
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_BYTES:
                    raise CatalogError(413, "Размер пакета превышает 4 МиБ.")
                body.extend(chunk)
    except (ClientDisconnect, TimeoutError):
        raise CatalogError(408, "Приём пакета прерван.") from None

    def import_body():
        package = parse_package(body)
        return storage.save(request.app.state.database_path, package, sha256(body).hexdigest())

    revision, created = await run_in_threadpool(import_body)
    response.status_code = 201 if created else 200
    return revision


@router.post("/convert", dependencies=[Depends(local_write)])
async def convert_document(request: Request) -> Conversion:
    slots = request.app.state.document_upload_slots
    if slots.locked():
        raise CatalogError(429, "Сервер обрабатывает другие загрузки. Повторите попытку позже.")
    async with slots:
        try:
            async with asyncio.timeout(30):
                filename, content = await receive_file(request, request.app.state.document_max_bytes)
            return await run_in_threadpool(convert, filename, content)
        except TimeoutError as error:
            raise CatalogError(408, "Истекло время приёма файла.") from error
        except RejectedUpload as error:
            raise CatalogError(error.status_code, str(error)) from error


@router.post("/revisions/{revision}/publish", dependencies=[Depends(local_write)])
def publish(request: Request, revision: str) -> Revision:
    return storage.transition(request.app.state.database_path, revision, "publish")


@router.post("/revisions/{revision}/activate", dependencies=[Depends(local_write)])
def activate(request: Request, revision: str) -> Revision:
    return storage.transition(request.app.state.database_path, revision, "activate")


@router.post("/revisions/{revision}/archive", dependencies=[Depends(local_write)])
def archive(request: Request, revision: str) -> Revision:
    return storage.transition(request.app.state.database_path, revision, "archive")


@router.post("/revisions/{revision}/deactivate", dependencies=[Depends(local_write)])
def deactivate(request: Request, revision: str) -> Revision:
    return storage.transition(request.app.state.database_path, revision, "deactivate")


@router.delete("/revisions/{revision}", dependencies=[Depends(local_write)], status_code=204)
def delete_revision(request: Request, revision: str) -> Response:
    storage.delete_archived(request.app.state.database_path, revision)
    return Response(status_code=204)
