from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...contracts import RegulatorySource, Requirement
from .models import Metadata, parse_package

router = APIRouter(prefix="/requirements", tags=["requirements"])
SOURCE = Path(__file__).with_name("requirements-117-2026-05-08.json")


class FixedRevision(Metadata):
    sha256: str
    requirement_count: int


class Catalog(BaseModel):
    revision: FixedRevision
    entries: list[Requirement]


@lru_cache(maxsize=1)
def catalog() -> Catalog:
    raw = SOURCE.read_bytes()
    package = parse_package(raw)
    revision = FixedRevision(**package.model_dump(exclude={"requirements"}),
                             sha256=sha256(raw).hexdigest(), requirement_count=len(package.requirements))
    entries = [
        Requirement(requirement_id=row.requirement_id, requirement_text=row.requirement_text,
                    source_reference=RegulatorySource(order_number=package.order_number,
                                                      revision=package.revision, clause=row.clause))
        for row in package.requirements
    ]
    return Catalog(revision=revision, entries=entries)


@router.get("")
def list_requirements() -> list[Requirement]:
    return catalog().entries


@router.get("/active")
def active_revision() -> FixedRevision:
    return catalog().revision


@router.get("/revisions")
def list_revisions() -> list[FixedRevision]:
    return [catalog().revision]


@router.get("/revisions/{revision}/requirements")
def revision_requirements(revision: str) -> list[Requirement]:
    if revision != catalog().revision.revision:
        raise HTTPException(404, "Редакция отсутствует в фиксированной базе.")
    return catalog().entries
