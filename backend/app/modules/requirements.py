from fastapi import APIRouter

from ..contracts import Requirement

router = APIRouter(prefix="/requirements", tags=["requirements"])


@router.get("", response_model=list[Requirement])
def list_requirements() -> list[Requirement]:
    return []
