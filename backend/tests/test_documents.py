import json
import logging
import os
import unittest
from collections import deque
from contextlib import AsyncExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID

from app.main import create_app
from app.modules.documents import storage
from pypdf import PageObject

from tests.document_fixtures import docx, paragraph, pdf

LIMIT = 8192
BOUNDARY = b"SyntheticTestBoundary"


def form(content: bytes, name: str = "sample.bin") -> bytes:
    return (
        b"--" + BOUNDARY + b'\r\nContent-Disposition: form-data; name="file"; filename="'
        + name.encode() + b'"\r\nContent-Type: application/octet-stream\r\n\r\n'
        + content + b"\r\n--" + BOUNDARY + b"--\r\n"
    )


class DocumentsApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async with AsyncExitStack() as stack:
            directory = stack.enter_context(TemporaryDirectory())
            self.db_path = Path(directory) / "inspector.sqlite3"
            self.app = create_app(self.db_path)
            with patch.dict(os.environ, {"FSTEC_DOCUMENT_MAX_BYTES": str(LIMIT)}):
                await stack.enter_async_context(self.app.router.lifespan_context(self.app))
            self.addAsyncCleanup(stack.pop_all().aclose)

    async def request(self, method, path, *, chunks=(), headers=()):
        received = deque(chunks or (b"",))
        sent = []

        async def receive():
            data = received.popleft()
            return {"type": "http.request", "body": data, "more_body": bool(received)}

        async def send(message):
            sent.append(message)

        await self.app({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1", "method": method, "scheme": "http",
            "path": path, "raw_path": path.encode(), "query_string": b"",
            "root_path": "", "headers": list(headers),
            "server": ("test", 80), "client": ("test", 54321),
        }, receive, send)
        return sent[0]["status"], json.loads(b"".join(item["body"] for item in sent[1:]))

    async def upload(self, content, name="sample.bin"):
        return await self.post_body(form(content, name))

    async def post_body(self, body, *, chunk_size=199, length=None):
        headers = [(b"content-type", b"multipart/form-data; boundary=" + BOUNDARY)]
        if length is not None:
            headers.append((b"content-length", str(length).encode()))
        return await self.request(
            "POST", "/api/v1/documents",
            chunks=[body[index:index + chunk_size] for index in range(0, len(body), chunk_size)],
            headers=headers,
        )

    async def documents(self):
        status, records = await self.request("GET", "/api/v1/documents")
        self.assertEqual(status, 200)
        return records

    def fragments(self, record):
        return storage.read_fragments(self.db_path, UUID(record["id"]))

    async def test_pdf_content_detection_page_locations_original_and_dashboard(self):
        content = pdf("Synthetic page one", "Synthetic page two")
        status, record = await self.upload(content, "../обезличенный.docx")
        self.assertEqual(status, 201)
        self.assertEqual(record["filename"], "обезличенный.docx")
        self.assertEqual(record["size_bytes"], len(content))
        self.assertEqual((record["format"], record["state"], record["issue"]), ("pdf", "extracted", None))
        self.assertEqual(await self.documents(), [record])
        self.assertEqual([item.location.page for item in self.fragments(record)], [1, 2])
        self.assertEqual([item.text for item in self.fragments(record)], ["Synthetic page one", "Synthetic page two"])
        with storage.connection(self.db_path) as db:
            internal, original = db.execute("SELECT storage_name, original FROM documents").fetchone()
        self.assertEqual(internal, f"{UUID(record['id']).hex}.pdf")
        self.assertEqual(original, content)
        self.assertNotIn("original", record)
        self.assertNotIn("fragments", record)
        status, summary = await self.request("GET", "/api/v1/dashboard/summary")
        self.assertEqual((status, summary["documents"]), (200, 1))

    async def test_docx_preserves_paragraph_and_table_order_and_marks_unknown(self):
        content = docx(
            paragraph("До заголовка")
            + paragraph("Раздел А", heading=True)
            + paragraph("Первый абзац")
            + "<w:tbl><w:tr><w:tc>" + paragraph("Текст ячейки") + "</w:tc></w:tr></w:tbl>"
            + paragraph("Раздел Б", heading=True) + paragraph("Последний абзац")
        )
        status, record = await self.upload(content, "sample.pdf")
        self.assertEqual(status, 201)
        self.assertEqual(record["format"], "docx")
        self.assertEqual(record["state"], "needs_review")
        self.assertEqual(record["issue"]["code"], "unknown_location")
        text = self.fragments(record)
        self.assertEqual(
            [item.text for item in text],
            ["До заголовка", "Раздел А", "Первый абзац", "Текст ячейки", "Раздел Б", "Последний абзац"],
        )
        self.assertEqual(text[0].location.kind, "unknown")
        self.assertEqual([item.location.section for item in text[1:]], ["Раздел А"] * 3 + ["Раздел Б"] * 2)

    async def test_docx_identified_section_and_empty_document(self):
        status, recognized = await self.upload(docx(paragraph("Раздел", heading=True) + paragraph("Абзац")))
        self.assertEqual((status, recognized["state"]), (201, "extracted"))
        status, empty = await self.upload(docx(paragraph("")))
        self.assertEqual((status, empty["state"], empty["issue"]["code"]), (201, "needs_review", "no_text"))
        self.assertFalse(self.fragments(empty))

    async def test_docx_unlinked_styles_do_not_create_source_locations(self):
        content = docx(paragraph("Свободный текст", heading=True), linked_styles=False)
        status, record = await self.upload(content)
        self.assertEqual((status, record["issue"]["code"]), (201, "unknown_location"))
        self.assertEqual(self.fragments(record)[0].location.kind, "unknown")

    async def test_docx_partial_limit_preserves_existing_fragments(self):
        content = docx(paragraph("Глава", heading=True) + paragraph("Продолжение"))
        with patch("app.modules.documents.docx.MAX_PARAGRAPHS", 1):
            status, record = await self.upload(content)
        self.assertEqual((status, record["state"], record["issue"]["code"]), (201, "needs_review", "partial_extraction"))
        self.assertEqual([item.text for item in self.fragments(record)], ["Глава"])

    async def test_invalid_empty_and_corrupt_inputs_leave_no_rows(self):
        for content, expected in (
            (b"plain text", 415),
            (b"", 422),
            (b"%PDF-1.7\nIncomplete", 422),
            (b"PK\x03\x04Incomplete", 422),
            (docx("<w:p>"), 422),
            (pdf("Synthetic", encrypted=True), 422),
        ):
            with self.subTest(expected=expected, signature=content[:5]):
                status, error = await self.upload(content, "sample.pdf")
                self.assertEqual(status, expected)
                self.assertIsInstance(error["detail"], str)
        self.assertEqual(await self.documents(), [])

    async def test_limits_and_streaming_upload_without_content_length(self):
        self.assertEqual(await self.request("GET", "/api/v1/documents/limits"), (200, {"max_size_bytes": LIMIT}))
        for length in (None, LIMIT + 50_000):
            status, error = await self.post_body(form(b"x" * (LIMIT + 1)), length=length)
            self.assertEqual(status, 413)
            self.assertIn(str(LIMIT), error["detail"])
        status, record = await self.upload(pdf("Synthetic").ljust(LIMIT, b" "))
        self.assertEqual((status, record["size_bytes"]), (201, LIMIT))

    async def test_rejects_malformed_or_incomplete_multipart(self):
        for body in (b"invalid", form(b"data").rsplit(b"--" + BOUNDARY, 1)[0]):
            status, _ = await self.post_body(body)
            self.assertEqual(status, 400)
        self.assertEqual(await self.documents(), [])

    async def test_docx_archive_and_xml_safety(self):
        with patch("app.modules.documents.docx.MAX_ARCHIVE_BYTES", 32):
            status, error = await self.upload(docx(paragraph("Синтетика")))
        self.assertEqual(status, 422)
        self.assertIn("распакованного", error["detail"])
        for content, message in (
            (docx(paragraph("Текст"), prefix="<!DOCTYPE document>"), "объявления XML"),
            (docx(paragraph("Текст"), extras={"../outside.txt": "synthetic"}), "элементы архива"),
            (docx(paragraph("Текст"), extras={"word/vbaProject.bin": "synthetic"}), "макросами"),
        ):
            with self.subTest(message=message):
                status, error = await self.upload(content)
                self.assertEqual(status, 422)
                self.assertIn(message, error["detail"])
        self.assertEqual(await self.documents(), [])

    async def test_scan_and_pdf_with_missing_text_page(self):
        status, scan = await self.upload(pdf(None, scan=True))
        self.assertEqual((status, scan["state"], scan["issue"]["code"]), (201, "needs_review", "no_text"))
        self.assertFalse(self.fragments(scan))
        status, partial = await self.upload(pdf("Synthetic", None, "Third", scan=True))
        self.assertEqual((status, partial["state"], partial["issue"]["code"]), (201, "needs_review", "partial_extraction"))
        self.assertEqual([item.location.page for item in self.fragments(partial)], [1, 3])
        self.assertIn("страницы: 2", partial["issue"]["message"])

    async def test_extraction_exception_and_parser_warning_are_reported(self):
        with patch.object(PageObject, "extract_text", side_effect=["First", ValueError("synthetic internal error")]):
            status, record = await self.upload(pdf("First", "Second"))
        self.assertEqual((status, record["state"]), (201, "needs_review"))
        self.assertEqual([item.text for item in self.fragments(record)], ["First"])
        self.assertNotIn("synthetic internal error", record["issue"]["message"])

        def warning(*args, **kwargs):
            logging.getLogger("pypdf.synthetic").warning("Do not expose this fixture warning")
            return "Fragment with a warning"

        with patch.object(PageObject, "extract_text", side_effect=warning):
            status, record = await self.upload(pdf("Synthetic"))
        self.assertEqual((status, record["issue"]["code"]), (201, "partial_extraction"))
        self.assertNotIn("fixture warning", record["issue"]["message"])

        with patch.object(PageObject, "extract_text", side_effect=ValueError("synthetic")):
            status, record = await self.upload(pdf("Synthetic"))
        self.assertEqual((status, record["state"], record["issue"]["code"]), (201, "failed", "extraction_failed"))

    async def test_write_error_rolls_back_record_and_original(self):
        with storage.connection(self.db_path) as db:
            db.executescript("""
                CREATE TRIGGER simulate_write_error BEFORE INSERT ON document_fragments
                BEGIN SELECT RAISE(ABORT, 'synthetic write error'); END;
            """)
        status, error = await self.upload(pdf("Synthetic"))
        self.assertEqual(status, 503)
        self.assertIn("сохранить", error["detail"])
        self.assertNotIn("synthetic", error["detail"])
        with storage.connection(self.db_path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM document_fragments").fetchone()[0], 0)

    async def test_busy_local_server_does_not_accept_another_upload(self):
        slots = self.app.state.document_upload_slots
        async with slots, slots:
            status, error = await self.upload(pdf("Synthetic"))
        self.assertEqual(status, 429)
        self.assertIn("другие загрузки", error["detail"])
        self.assertEqual(await self.documents(), [])
