import sqlite3
from ipaddress import ip_address

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel

from .dialogs import DialogDeleted

class ErrorResponse(BaseModel):
    detail: str


class LocalActionRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(
                    422, "Проверьте идентификаторы, список документов и поля запроса."
                ) from None
            except DialogDeleted as error:
                raise HTTPException(410, str(error)) from None
            except sqlite3.Error:
                raise HTTPException(503, "Локальное хранилище недоступно. Повторите попытку позже.") from None

        return handle


def local_action(request: Request) -> None:
    try:
        local = request.client is not None and ip_address(request.client.host).is_loopback
        hostname = request.url.hostname
        port = request.url.port
    except ValueError:
        local, hostname, port = False, None, None
    if (
        not local or hostname not in {"localhost", "127.0.0.1", "::1"}
        or (port is not None and port == 0)
        or request.headers.get("x-inspector-action") != "1"
    ):
        raise HTTPException(403, "Операция доступна только через локальный интерфейс.")
