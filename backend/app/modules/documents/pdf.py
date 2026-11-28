import logging
from contextvars import ContextVar
from io import BytesIO

from pypdf import PdfReader, apply_configuration
from pypdf.errors import LimitReachedError

from ...contracts import PdfLocation
from .models import DocumentIssue, Extraction, Fragment, RejectedUpload

MAX_PAGES = 500
MAX_TEXT_CHARS = 2_000_000
STREAM_LIMIT = 8 * 1024 * 1024
diagnostic = ContextVar("pdf_diagnostic", default=False)


class ParserDiagnostics(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Preserve the fact of a warning without logging its untrusted content.
        diagnostic.set(True)


parser_logger = logging.getLogger("pypdf")
parser_logger.addHandler(ParserDiagnostics(level=logging.WARNING))
parser_logger.propagate = False


def extract(content: bytes) -> Extraction:
    token = diagnostic.set(False)
    try:
        with apply_configuration(
            jbig2dec_binary=None,
            maximum_declared_stream_length=STREAM_LIMIT,
            array_based_stream_maximum_output_length=STREAM_LIMIT,
            zlib_maximum_output_length=STREAM_LIMIT,
            lzw_maximum_output_length=STREAM_LIMIT,
            run_length_maximum_output_length=STREAM_LIMIT,
            brotli_maximum_output_length=STREAM_LIMIT,
            stream_decoding_work_maximum_length=2 * STREAM_LIMIT,
            stream_parsing_work_maximum_count=500_000,
            page_tree_maximum_entries=MAX_PAGES,
            page_tree_maximum_page_entries=12_000,
            xform_maximum_invocations_per_extraction=200,
        ):
            return read_pages(content)
    finally:
        diagnostic.reset(token)


def read_pages(content: bytes) -> Extraction:
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise RejectedUpload(422, "PDF защищён паролем или зашифрован. Сохраните незашифрованную копию.")
        page_count = len(reader.pages)
    except RejectedUpload:
        raise
    except LimitReachedError as error:
        raise RejectedUpload(422, "PDF превышает допустимые пределы сложности или числа страниц.") from error
    except Exception as error:
        raise RejectedUpload(422, "Не удалось прочитать структуру PDF. Проверьте файл и сохраните копию заново.") from error

    if page_count < 1 or page_count > MAX_PAGES:
        raise RejectedUpload(422, f"PDF должен содержать от 1 до {MAX_PAGES} страниц.")

    reader_warning = diagnostic.get()
    result = Extraction("pdf")
    empty_pages = error_pages = total_chars = 0
    affected_pages: list[int] = []
    limit_reached = False
    for number, page in enumerate(reader.pages, start=1):
        diagnostic.set(False)
        try:
            text = page.extract_text().strip()
        except Exception:
            text = ""
            diagnostic.set(True)
        warning = diagnostic.get()
        if warning:
            error_pages += 1
        elif not text:
            empty_pages += 1
        if warning or not text:
            affected_pages.append(number)
        if not text:
            continue
        total_chars += len(text)
        if total_chars > MAX_TEXT_CHARS:
            limit_reached = True
            affected_pages.append(number)
            break
        result.fragments.append(Fragment(text, PdfLocation(kind="pdf_page", page=number)))

    if not result.fragments:
        if error_pages or reader_warning or limit_reached:
            message = "Не удалось надёжно извлечь текст из PDF."
            if limit_reached:
                message = "Объём текста PDF превышает допустимый предел извлечения."
            result.issue = DocumentIssue(code="extraction_failed", message=message)
        else:
            result.issue = DocumentIssue(
                code="no_text", message="В PDF не найден текстовый слой. Для скана потребуется отдельное распознавание."
            )
    elif affected_pages or reader_warning:
        message = "Текст PDF извлечён не полностью или требует проверки."
        if affected_pages:
            numbers = ", ".join(map(str, sorted(set(affected_pages))[:8]))
            message += f" Проверьте страницы: {numbers}."
        if empty_pages:
            message += " На части страниц не найден текстовый слой."
        if limit_reached:
            message += " Достигнут предел объёма текста. Обработка оставшихся страниц остановлена."
        result.issue = DocumentIssue(code="partial_extraction", message=message)
    return result
