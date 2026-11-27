from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatStatus(BaseModel):
    state: Literal["unavailable", "ready"]


@router.get("/status", response_model=ChatStatus)
def chat_status() -> ChatStatus:
    return ChatStatus(state="unavailable")
