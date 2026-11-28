import logging
import re

from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from starlette.requests import ClientDisconnect, Request

from .models import RejectedUpload

MULTIPART_OVERHEAD = 16 * 1024
INVALID_FORM = "Передайте один файл в поле file формы multipart/form-data."

# Parser diagnostics can incorporate untrusted input. Return sanitized errors instead.
parser_logger = logging.getLogger("python_multipart")
parser_logger.addHandler(logging.NullHandler())
parser_logger.propagate = False


def too_large(max_bytes: int) -> RejectedUpload:
    return RejectedUpload(413, f"Файл или запрос превышает допустимый размер. Максимум для файла — {max_bytes} байт.")


class FilePart:
    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes
        self.body = bytearray()
        self.field = bytearray()
        self.value = bytearray()
        self.header_bytes = 0
        self.disposition: bytes | None = None
        self.filename: str | None = None
        self.started = False
        self.finished = False

    def begin(self) -> None:
        if self.started:
            raise RejectedUpload(400, INVALID_FORM)
        self.started = True

    def append_header(self, target: bytearray, data: bytes, start: int, end: int) -> None:
        self.header_bytes += end - start
        if self.header_bytes > MULTIPART_OVERHEAD:
            raise too_large(self.max_bytes)
        target.extend(data[start:end])

    def header_field(self, data: bytes, start: int, end: int) -> None:
        self.append_header(self.field, data, start, end)

    def header_value(self, data: bytes, start: int, end: int) -> None:
        self.append_header(self.value, data, start, end)

    def header_end(self) -> None:
        if self.field.lower() == b"content-disposition":
            if self.disposition is not None:
                raise RejectedUpload(400, INVALID_FORM)
            self.disposition = bytes(self.value)
        self.field.clear()
        self.value.clear()

    def headers_finished(self) -> None:
        disposition, options = parse_options_header(self.disposition)
        if disposition != b"form-data" or options.get(b"name") != b"file" or b"filename" not in options:
            raise RejectedUpload(400, INVALID_FORM)
        self.filename = options[b"filename"].decode("utf-8", errors="replace")

    def append_body(self, data: bytes, start: int, end: int) -> None:
        if len(self.body) + end - start > self.max_bytes:
            raise too_large(self.max_bytes)
        self.body.extend(data[start:end])

    def finish(self) -> None:
        self.finished = True


async def receive_file(request: Request, max_bytes: int) -> tuple[str, bytes]:
    media_type, options = parse_options_header(request.headers.get("content-type"))
    boundary = options.get(b"boundary", b"")
    if media_type != b"multipart/form-data":
        raise RejectedUpload(415, INVALID_FORM)
    if not re.fullmatch(rb"[0-9A-Za-z'()+_,./:=? -]{1,70}", boundary):
        raise RejectedUpload(400, INVALID_FORM)

    max_request = max_bytes + MULTIPART_OVERHEAD
    content_length = request.headers.get("content-length")
    if content_length is not None:
        if not re.fullmatch(r"[0-9]{1,20}", content_length):
            raise RejectedUpload(400, "Некорректный размер запроса.")
        if int(content_length) > max_request:
            raise too_large(max_bytes)

    part = FilePart(max_bytes)
    parser = MultipartParser(boundary, {
        "on_part_begin": part.begin,
        "on_header_field": part.header_field,
        "on_header_value": part.header_value,
        "on_header_end": part.header_end,
        "on_headers_finished": part.headers_finished,
        "on_part_data": part.append_body,
        "on_end": part.finish,
    })
    size = 0
    try:
        async for chunk in request.stream():
            size += len(chunk)
            if size > max_request:
                raise too_large(max_bytes)
            if chunk:
                parser.write(chunk)
        parser.finalize()
    except (MultipartParseError, ClientDisconnect) as error:
        raise RejectedUpload(400, "Загрузка прервана или форма повреждена.") from error

    if not part.finished or part.filename is None:
        raise RejectedUpload(400, INVALID_FORM)
    if not part.body:
        raise RejectedUpload(422, "Файл пуст. Выберите PDF или DOCX с содержимым.")
    return part.filename, bytes(part.body)
