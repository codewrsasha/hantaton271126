import json
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, field_validator, model_validator

Key = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")]
Label = Annotated[str, StringConstraints(min_length=1, max_length=512)]
State = Literal["draft", "published", "archived"]
MAX_BYTES = 4 * 1024 * 1024


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Entry(ClosedModel):
    requirement_id: Key
    clause: Label
    requirement_text: str = Field(min_length=1, max_length=64000)

    @field_validator("clause", "requirement_text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("blank or padded text")
        return value


class Metadata(ClosedModel):
    order_number: Literal["117"]
    revision: Key
    revision_date: date
    obtained_on: date
    source: Label


class Package(Metadata):
    requirements: list[Entry] = Field(min_length=1, max_length=10000)

    @field_validator("revision_date", "obtained_on", mode="before")
    @classmethod
    def iso_date(cls, value):
        if not isinstance(value, str) or len(value) != 10 or value[4:5] != "-" or value[7:8] != "-":
            raise ValueError("expected YYYY-MM-DD")
        return date.fromisoformat(value)

    @field_validator("source")
    @classmethod
    def source_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("empty source")
        return value

    @model_validator(mode="after")
    def unique_entries(self):
        for field in ("requirement_id", "clause"):
            if len({getattr(entry, field) for entry in self.requirements}) != len(self.requirements):
                raise ValueError("duplicate " + field)
        return self


class Revision(Metadata):
    sha256: str
    imported_at: datetime
    reviewed_at: datetime | None
    state: State
    active: bool
    requirement_count: int


class ErrorResponse(BaseModel):
    detail: str


class CatalogError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def distinct_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def parse_package(raw: bytes) -> Package:
    try:
        data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=distinct_keys)
        return Package.model_validate(data)
    except ValidationError as error:
        issue = error.errors(include_input=False, include_context=False)[0]
        fields = set(Package.model_fields) | set(Entry.model_fields)
        location = ".".join(str(part) for part in issue["loc"] if isinstance(part, int) or part in fields)
        message = "Проверьте обязательные поля, типы и значения пакета."
        if not location and issue["type"] == "value_error":
            message = "Идентификаторы требований и пункты должны быть уникальны в редакции."
        raise CatalogError(422, f"{location}. {message}" if location else message) from None
    except (ValueError, RecursionError):
        raise CatalogError(422, "Ожидается JSON в UTF-8 с уникальными ключами.") from None
