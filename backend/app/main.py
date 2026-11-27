import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import FRONTEND_DIST, database_path
from .db import check_database
from .modules import analysis, chat, dashboard, documents, reports, requirements


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["sqlite"] = "sqlite"


def create_app(db_path: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        path = db_path if db_path is not None else database_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        check_database(path)
        app.state.database_path = path
        yield

    app = FastAPI(
        title="FSTEC Inspector",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    api = APIRouter(prefix="/api/v1")

    @api.get("/health", response_model=Health, tags=["system"])
    def health(request: Request) -> Health:
        try:
            check_database(request.app.state.database_path)
        except sqlite3.Error as error:
            raise HTTPException(503, "SQLite is unavailable") from error
        return Health()

    for module in (dashboard, documents, requirements, analysis, reports, chat):
        api.include_router(module.router)

    app.include_router(api)
    if (FRONTEND_DIST / "index.html").is_file():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app


app = create_app()
