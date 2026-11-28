import codecs
import re
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import PurePosixPath

from pydantic import BaseModel
from striprtf.striprtf import rtf_to_text

from ..documents import display_filename, docx, pdf
from .models import MAX_BYTES, CatalogError

NUMBERED = re.compile(r"^[ \t]*(?P<clause>[0-9]+(?:\.[0-9]+)+|[0-9]+(?=[.)]))[.)]?[ \t]+(?=\S)", re.MULTILINE)
TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".html", ".htm"}


class DraftEntry(BaseModel):
    requirement_id: str
    clause: str
    requirement_text: str


class DraftPackage(BaseModel):
    order_number: str = "117"
    revision: str
    revision_date: str = ""
    obtained_on: str = ""
    source: str
    requirements: list[DraftEntry]


class Conversion(BaseModel):
    package: DraftPackage
    warnings: list[str]


class TextHTML(HTMLParser):
    hidden_tags = {"script", "style", "head", "template"}
    blocks = {"p", "br", "div", "li", "tr", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.hidden_tags:
            self.hidden += 1
        elif not self.hidden and tag in self.blocks:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.hidden_tags and self.hidden:
            self.hidden -= 1
        elif not self.hidden and tag in self.blocks:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def decode_text(content: bytes) -> str:
    if content.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return content.decode("utf-16")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1251")


def extract_text(filename: str, content: bytes) -> tuple[str, list[str]]:
    if content.startswith((b"%PDF-", b"PK\x03\x04")):
        extracted = pdf.extract(content) if content.startswith(b"%PDF-") else docx.extract(content)
        return "\n".join(part.text for part in extracted.fragments), [extracted.issue.message] if extracted.issue else []
    extension = PurePosixPath(filename).suffix.lower()
    try:
        if content.startswith(b"{\\rtf"):
            if re.search(rb"\\(?:bin|object)\b", content):
                raise CatalogError(422, "RTF содержит встроенные объекты или двоичные данные. Сохраните только текст.")
            return rtf_to_text(content.decode("latin-1")), []
        if extension not in TEXT_EXTENSIONS:
            raise CatalogError(415, "Поддерживаются PDF с текстом, DOCX, RTF, TXT, Markdown, RST, CSV, TSV и HTML.")
        value = decode_text(content)
        if any(ord(char) < 32 and char not in "\r\n\t\f" for char in value):
            raise CatalogError(422, "Текстовый файл содержит двоичные данные.")
        if extension in {".html", ".htm"}:
            parser = TextHTML()
            parser.feed(value)
            parser.close()
            value = "".join(parser.parts)
        return value, []
    except (ValueError, LookupError, IndexError) as error:
        raise CatalogError(422, "Не удалось прочитать документ. Проверьте формат и кодировку.") from error


def convert(filename: str, content: bytes) -> Conversion:
    filename = display_filename(filename, "txt")
    value, warnings = extract_text(filename, content)
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not value:
        raise CatalogError(422, "Текст не найден. Для скана сначала выполните распознавание текста.")

    matches = list(NUMBERED.finditer(value))
    parts = [("", value[:matches[0].start()] if matches else value)]
    ends = [match.start() for match in matches[1:]] + [len(value)]
    parts.extend((match["clause"], value[match.start():end]) for match, end in zip(matches, ends))
    used: set[str] = set()
    entries: list[DraftEntry] = []
    for clause, body in parts:
        if not body.strip():
            continue
        # Leave ambiguous clauses empty for manual reconciliation.
        unique_clause = clause if clause not in used else ""
        used.add(clause)
        entries.append(DraftEntry(requirement_id=f"item-{len(entries) + 1}", clause=unique_clause,
                                  requirement_text=body.strip()))
    if any(not entry.clause for entry in entries):
        warnings.append("У некоторых фрагментов нет однозначного номера. Укажите пункт вручную или исключите служебный текст.")
    if len(entries) > 10000 or any(len(entry.requirement_text) > 64000 for entry in entries):
        warnings.append("Для сохранения разбейте длинные фрагменты или документ на меньшие части.")
    digest = sha256(content).hexdigest()
    result = DraftPackage(revision=f"117-{digest[:16]}", source=f"Файл {filename}. SHA-256 оригинала: {digest}",
                          requirements=entries)
    if len(result.model_dump_json().encode("utf-8")) > MAX_BYTES:
        warnings.append("Полученный JSON превышает 4 МиБ. Для импорта разделите пакет.")
    return Conversion(package=result, warnings=warnings)
