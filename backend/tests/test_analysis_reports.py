import json
import sqlite3
import unittest
from contextlib import AsyncExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from app.main import create_app
from app.db import transaction
from app.ollama import ModelError
from app.modules.requirements import Catalog, FixedRevision
from app.contracts import Requirement, RegulatorySource

from tests.document_fixtures import docx, paragraph, pdf
from tests.test_documents import BOUNDARY, form

ANALYSES = "/api/v1/analyses"
REPORTS = "/api/v1/reports"
CATALOG = "/api/v1/requirements/revisions"
PDF_TEXT = "Synthetic telemetry encryption is enabled. <verification> & fixture"
DOCX_TEXT = "Synthetic telemetry encryption is disabled. Другой документ."
SECTION_TITLE = "Учебный раздел"


class AnalysisReportsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async with AsyncExitStack() as stack:
            self.db_path = Path(stack.enter_context(TemporaryDirectory())) / "test.sqlite3"
            self.app = create_app(self.db_path)
            await stack.enter_async_context(self.app.router.lifespan_context(self.app))
            self.addAsyncCleanup(stack.pop_all().aclose)

    async def request(self, method, path, body=b"", *, content=b"application/json", marker=True, dialog=None):
        headers = [(b"host", b"localhost:8000"), (b"content-type", content)]
        if dialog is not None:
            headers.append((b"x-dialog-id", str(dialog).encode()))
        if marker:
            headers.extend([(b"x-inspector-action", b"1"), (b"x-catalog-action", b"1")])
        messages = []

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            messages.append(message)

        await self.app({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1", "method": method, "scheme": "http",
            "path": path, "raw_path": path.encode(), "query_string": b"",
            "root_path": "", "headers": headers,
            "server": ("localhost", 8000), "client": ("127.0.0.1", 12345),
        }, receive, send)
        return (
            messages[0]["status"],
            dict(messages[0]["headers"]),
            b"".join(message["body"] for message in messages[1:]),
        )

    async def api(self, method, path, data=None, *, marker=True, dialog=None):
        code, _, body = await self.request(
            method, path, json.dumps(data).encode() if data is not None else b"", marker=marker, dialog=dialog,
        )
        return code, json.loads(body)

    async def activate(self, revision, *, query="Synthetic telemetry encryption <policy>"):
        data = {
            "order_number": "117", "revision": revision, "revision_date": "2000-01-01",
            "obtained_on": "2000-01-02", "source": "Учебный источник <реквизит>",
            "requirements": [
                {"requirement_id": "SYN-01", "clause": "Учебный пункт <A>", "requirement_text": query},
                {"requirement_id": "SYN-02", "clause": "Учебный пункт Б", "requirement_text": "unrelated zebra botanical"},
            ],
        }
        meta = FixedRevision(order_number="117", revision=revision, revision_date=data["revision_date"],
                             obtained_on=data["obtained_on"], source=data["source"], sha256="a" * 64,
                             requirement_count=len(data["requirements"]))
        entries = [Requirement(requirement_id=row["requirement_id"], requirement_text=row["requirement_text"],
                    source_reference=RegulatorySource(order_number="117", revision=revision, clause=row["clause"]))
                   for row in data["requirements"]]
        if hasattr(self, "catalog_patch"):
            self.catalog_patch.stop()
        self.catalog_patch = patch("app.modules.analysis.catalog.catalog", return_value=Catalog(revision=meta, entries=entries))
        self.catalog_patch.start()
        self.addCleanup(self.catalog_patch.stop)

    async def upload(self, content, filename, *, dialog=None):
        status, _, response = await self.request(
            "POST", "/api/v1/documents", form(content, filename),
            content=b"multipart/form-data; boundary=" + BOUNDARY, dialog=dialog,
        )
        self.assertEqual(status, 201)
        return json.loads(response)["id"]

    async def launch(self, *document_ids, **fields):
        status, run = await self.api("POST", ANALYSES, {"document_ids": list(document_ids), **fields})
        self.assertEqual(status, 201, run)
        self.assertEqual(run["state"], "completed")
        return run

    async def test_documents_analyses_and_reports_are_isolated_by_dialog(self):
        await self.activate("synthetic-a")
        first, second = uuid4(), uuid4()
        documents = "/api/v1/documents"
        doc = await self.upload(pdf(PDF_TEXT), "first.pdf", dialog=first)
        fragments = f"{documents}/{doc}/fragments"
        self.assertEqual(await self.api("GET", documents, dialog=second), (200, []))
        self.assertEqual(await self.api("GET", documents), (200, []))
        self.assertEqual((await self.api("GET", documents, dialog="invalid"))[0], 422)
        self.assertEqual((await self.api("GET", fragments, dialog=second))[0], 404)
        self.assertEqual((await self.api("GET", fragments, dialog=first))[1][0]["text"], PDF_TEXT)
        other = await self.upload(docx(paragraph("Second dialog")), "second.docx", dialog=second)
        self.assertEqual([item["id"] for item in (await self.api("GET", documents, dialog=first))[1]], [doc])
        self.assertEqual([item["id"] for item in (await self.api("GET", documents, dialog=second))[1]], [other])

        data = {"document_ids": [doc]}
        self.assertEqual((await self.api("POST", ANALYSES, data, dialog=second))[0], 404)
        status, run = await self.api("POST", ANALYSES, data, dialog=first)
        self.assertEqual((status, run["state"]), (201, "completed"))
        url = f"{ANALYSES}/{run['id']}"
        self.assertEqual(await self.api("GET", ANALYSES, dialog=second), (200, []))
        self.assertEqual((await self.api("GET", url, dialog=second))[0], 404)
        self.assertEqual((await self.api(
            "PUT", f"{url}/results/SYN-01/review", {"comment": "Синтетический отзыв"}, dialog=second,
        ))[0], 404)

        data = {"analysis_id": run["id"]}
        self.assertEqual((await self.api("POST", REPORTS, data, dialog=second))[0], 404)
        status, report = await self.api("POST", REPORTS, data, dialog=first)
        self.assertEqual(status, 201)
        download = f"{REPORTS}/{report['id']}/download"
        self.assertEqual(await self.api("GET", REPORTS, dialog=second), (200, []))
        self.assertEqual((await self.request("GET", download, dialog=second))[0], 404)
        self.assertEqual((await self.request("GET", download, dialog=first))[0], 200)
        _, summary = await self.api("GET", "/api/v1/dashboard/summary", dialog=second)
        self.assertEqual((summary["documents"], summary["analyses"], summary["reports"]), (1, 0, 0))

    async def test_chat_grounds_response_in_catalog_and_current_dialog_only(self):
        await self.activate("synthetic-a")
        first, second = uuid4(), uuid4()
        doc = await self.upload(pdf(PDF_TEXT), "own.pdf", dialog=first)
        await self.upload(pdf("Synthetic telemetry encryption hidden"), "other.pdf", dialog=second)
        path = "/api/v1/chat/messages"
        data = {"question": "Synthetic telemetry encryption", "history": [{"question": "first question", "answer": "first answer"}]}
        with patch("app.ollama.answer", return_value="См. [Н1] и [Д1].") as answer:
            code, reply = await self.api("POST", path, data, dialog=first)
            self.assertEqual(code, 200)
            self.assertEqual(reply["answer"], "См. [Н1] и [Д1].")
            self.assertEqual(reply["citations"][0]["id"], "SYN-01")
            self.assertEqual(reply["document_evidence"][0]["document_id"], doc)
            self.assertEqual(reply["document_evidence"][0]["location"], {"kind": "pdf_page", "page": 1})
            messages = answer.call_args.args[0]
            self.assertEqual([item["role"] for item in messages], ["system", "user"])
            source = json.loads(messages[1]["content"])
            self.assertEqual(source["предыдущая переписка"], data["history"])
            self.assertEqual([item["filename"] for item in source["файлы"].values()], ["own.pdf"])
            self.assertNotIn("hidden", messages[1]["content"])
            self.assertEqual((await self.api("POST", path, data, dialog=first, marker=False))[0], 403)
            self.assertEqual((await self.api("POST", path, data))[0], 422)
            self.assertEqual(answer.call_count, 1)

    async def test_chat_recovers_after_local_model_failure_and_timeout(self):
        path = "/api/v1/chat/messages"
        data = {"question": "Синтетический вопрос"}
        dialog = uuid4()
        with patch("app.ollama.answer", side_effect=ModelError("Модель недоступна.")):
            self.assertEqual(await self.api("POST", path, data, dialog=dialog), (503, {"detail": "Модель недоступна."}))
        with patch("app.ollama.answer", side_effect=TimeoutError):
            self.assertEqual((await self.api("POST", path, data, dialog=dialog))[0], 504)
        with patch("app.ollama.answer", return_value="Ответ тестовой модели."):
            self.assertEqual((await self.api("POST", path, data, dialog=dialog))[0], 200)

    async def test_chat_reads_selected_document_and_reports_limits(self):
        first, second = uuid4(), uuid4()
        source = await self.upload(pdf("Synthetic procedure", "Last page"), "own.pdf", dialog=first)
        other = await self.upload(docx(paragraph(SECTION_TITLE, heading=True) + paragraph(DOCX_TEXT)),
                                  "own.docx", dialog=first)
        foreign = await self.upload(pdf("Other dialog"), "foreign.pdf", dialog=second)
        scan = await self.upload(pdf(None, scan=True), "scan.pdf", dialog=first)
        long_pdf = await self.upload(pdf(*(f"Synthetic page {i}" for i in range(1, 9))), "long.pdf", dialog=first)
        path = "/api/v1/chat/messages"
        with patch("app.ollama.answer", return_value="Ответ по файлу.") as answer:
            code, result = await self.api("POST", path, {"question": "О чём собственно own.pdf?"}, dialog=first)
            self.assertEqual(code, 200)
            self.assertEqual([item["document_id"] for item in result["document_evidence"]], [source, source])
            self.assertEqual([item["location"]["page"] for item in result["document_evidence"]], [1, 2])
            _, result = await self.api("POST", path, {"question": "Кратко перескажи", "document_id": other}, dialog=first)
            self.assertEqual(result["document_evidence"][0]["location"], {"kind": "docx_section", "section": SECTION_TITLE})
            self.assertIn(DOCX_TEXT, result["document_evidence"][0]["excerpt"])
            _, result = await self.api("POST", path, {"question": "Кратко перескажи", "document_id": long_pdf}, dialog=first)
            self.assertIn("часть извлечённого текста", result["document_note"])
            self.assertEqual([item["location"]["page"] for item in result["document_evidence"]], [1, 3, 5, 8])
            _, result = await self.api("POST", path, {"question": "Прочитай", "document_id": scan}, dialog=first)
            self.assertFalse(result["generated"])
            self.assertIn("извлечённого текста нет", result["document_note"])
            code, _ = await self.api("POST", path, {"question": "Прочитай", "document_id": foreign}, dialog=first)
            self.assertEqual(code, 404)
            self.assertEqual(answer.call_count, 3)

    async def test_deleting_dialog_removes_scoped_records_and_prevents_reuse(self):
        first, second = uuid4(), uuid4()
        source = await self.upload(pdf(PDF_TEXT), "delete.pdf", dialog=first)
        keep = await self.upload(pdf(PDF_TEXT), "keep.pdf", dialog=second)
        code, run = await self.api("POST", ANALYSES, {"document_ids": [source]}, dialog=first)
        self.assertEqual(code, 201)
        code, report = await self.api("POST", REPORTS, {"analysis_id": run["id"]}, dialog=first)
        self.assertEqual(code, 201)
        deletion = f"/api/v1/chat/dialogs/{first}"
        self.assertEqual((await self.request("DELETE", deletion, marker=False))[0], 403)
        for _ in range(2):
            code, _, body = await self.request("DELETE", deletion)
            self.assertEqual((code, body), (204, b""))
        for table in ("analysis_reports", "analysis_runs"):
            with transaction(self.db_path) as db:
                self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
        with transaction(self.db_path) as db:
            self.assertEqual(db.execute("SELECT id FROM documents").fetchall(), [(keep,)])
            self.assertEqual(db.execute("SELECT document_id FROM document_fragments").fetchall(), [(keep,)])
        code, _, _ = await self.request("POST", "/api/v1/documents", form(pdf("Delayed upload")),
                                        content=b"multipart/form-data; boundary=" + BOUNDARY, dialog=first)
        self.assertEqual(code, 410)
        self.assertEqual((await self.api("POST", "/api/v1/chat/messages", {"question": "Прочитай"}, dialog=first))[0], 410)

    async def test_existing_documents_and_analyses_are_migrated_to_legacy_dialog(self):
        await self.activate("synthetic-a")
        doc = await self.upload(pdf(PDF_TEXT), "existing.pdf")
        run = await self.launch(doc)
        status, report = await self.api("POST", REPORTS, {"analysis_id": run["id"]})
        self.assertEqual(status, 201)

        with transaction(self.db_path) as db:
            db.executescript("""
                DROP INDEX documents_dialog_idx;
                DROP INDEX analysis_dialog_idx;
                ALTER TABLE documents DROP COLUMN dialog_id;
                ALTER TABLE analysis_runs DROP COLUMN dialog_id;
            """)

        async with self.app.router.lifespan_context(self.app):
            documents = "/api/v1/documents"
            self.assertEqual([item["id"] for item in (await self.api("GET", documents))[1]], [doc])
            self.assertEqual(await self.api("GET", documents, dialog=uuid4()), (200, []))
            self.assertEqual((await self.api("GET", f"{documents}/{doc}/fragments"))[1][0]["text"], PDF_TEXT)
            self.assertEqual(await self.api("GET", ANALYSES), (200, [run]))
            self.assertEqual(await self.api("GET", REPORTS), (200, [report]))

    async def test_active_revision_is_pinned_and_all_requirements_are_present(self):
        await self.activate("synthetic-a")
        identifier = await self.upload(pdf("First page only", PDF_TEXT), "<source>.pdf")
        run = await self.launch(identifier)
        self.assertEqual(run["revision"], "synthetic-a")
        self.assertEqual(run["document_ids"], [identifier])
        self.assertTrue(run["created_at"].endswith("Z"))
        self.assertEqual([item["requirement_id"] for item in run["results"]], ["SYN-01", "SYN-02"])
        first, second = run["results"]
        self.assertEqual(first["source_reference"], {
            "order_number": "117", "revision": "synthetic-a", "clause": "Учебный пункт <A>",
        })
        self.assertEqual(first["evidence"][0], {
            "document_id": identifier, "filename": "<source>.pdf", "excerpt": PDF_TEXT,
            "location": {"kind": "pdf_page", "page": 2}, "relation": "context",
        })
        self.assertEqual(first["status"], "требуется проверка")
        self.assertIsNone(first["confidence"])
        self.assertEqual((second["status"], second["evidence"]), ("недостаточно данных", []))
        await self.activate("synthetic-b", query="Synthetic revision replacement")
        self.assertEqual(await self.api("GET", f"{ANALYSES}/{run['id']}"), (200, run))
        self.assertEqual((await self.api("GET", ANALYSES))[1], [run])
        code, _ = await self.api("POST", ANALYSES, {"document_ids": [identifier], "revision": "synthetic-a"})
        self.assertEqual(code, 409)
        fresh = await self.launch(identifier, revision="synthetic-b")
        self.assertEqual(fresh["results"][0]["source_reference"]["revision"], "synthetic-b")

    async def test_conflicting_candidates_remain_context_and_expert_review_preserves_original(self):
        await self.activate("synthetic-a")
        pdf_id = await self.upload(pdf(PDF_TEXT), "sample.pdf")
        docx_id = await self.upload(docx(paragraph(SECTION_TITLE, heading=True) + paragraph(DOCX_TEXT)), "sample.docx")
        run = await self.launch(pdf_id, docx_id)
        original = run["results"][0]
        self.assertEqual(original["status"], "требуется проверка")
        self.assertEqual([item["relation"] for item in original["evidence"]], ["context", "context"])
        second = original["evidence"][1]
        self.assertEqual(second["excerpt"], DOCX_TEXT)
        self.assertEqual(second["location"], {"kind": "docx_section", "section": SECTION_TITLE})
        url = f"{ANALYSES}/{run['id']}/results/SYN-01/review"
        for request in (
            {"comment": "   "},
            {"comment": "Синтетика", "corrected_status": "не соответствует"},
            {"comment": "Синтетика", "evidence_relations": {"8": "supports"}},
        ):
            self.assertEqual((await self.api("PUT", url, request))[0], 422)
        code, reviewed = await self.api("PUT", url, {
            "comment": "  Сверка синтетического противоречия.  ", "corrected_status": "не соответствует",
            "evidence_relations": {"0": "supports", "1": "contradicts"},
        })
        self.assertEqual(code, 200)
        self.assertEqual(reviewed["review"]["comment"], "Сверка синтетического противоречия.")
        self.assertEqual(reviewed["review"]["corrected_status"], "не соответствует")
        for key in ("status", "evidence", "explanation"):
            self.assertEqual(reviewed[key], original[key])
        self.assertEqual((await self.api("GET", f"{ANALYSES}/{run['id']}"))[1]["results"][0], reviewed)

    async def test_partial_unknown_and_empty_documents_never_prove_compliance(self):
        await self.activate("synthetic-a")
        partial_id = await self.upload(pdf(PDF_TEXT, None, scan=True), "partial.pdf")
        unknown_id = await self.upload(docx(paragraph(DOCX_TEXT)), "unknown.docx")
        scan_id = await self.upload(pdf(None, scan=True), "scan.pdf")
        run = await self.launch(partial_id, unknown_id, scan_id)
        self.assertEqual([doc["fragment_count"] for doc in run["documents"]], [1, 1, 0])
        self.assertEqual([doc["issue"]["code"] for doc in run["documents"]],
                         ["partial_extraction", "unknown_location", "no_text"])
        result = run["results"][0]
        self.assertIn("ограничения извлечения", result["explanation"])
        self.assertIn("точное местоположение", result["explanation"])
        unknown_index = next(i for i, item in enumerate(result["evidence"]) if item["document_id"] == unknown_id)
        self.assertEqual(result["evidence"][unknown_index]["location"], {"kind": "unknown"})
        code, _ = await self.api("PUT", f"{ANALYSES}/{run['id']}/results/SYN-01/review", {
            "comment": "Проверка ограничения", "corrected_status": "соответствует",
            "evidence_relations": {str(unknown_index): "supports"},
        })
        self.assertEqual(code, 422)
        empty_run = await self.launch(scan_id)
        self.assertTrue(all(item["status"] == "недостаточно данных" and not item["evidence"]
                            for item in empty_run["results"]))

    async def test_missing_inputs_and_storage_errors(self):
        document_id = str(uuid4())
        self.assertEqual((await self.api("POST", ANALYSES, {"document_ids": [document_id]}))[0], 404)
        await self.activate("synthetic-a")
        for ids in ([], ["not-a-uuid"], [document_id, document_id]):
            code, error = await self.api("POST", ANALYSES, {"document_ids": ids})
            self.assertEqual(code, 422)
            self.assertIsInstance(error["detail"], str)
        self.assertEqual((await self.api("POST", ANALYSES, {"document_ids": [document_id]}))[0], 404)
        self.assertEqual((await self.api("POST", ANALYSES, {"document_ids": [document_id]}, marker=False))[0], 403)
        self.assertEqual((await self.api("GET", f"{ANALYSES}/{uuid4()}"))[0], 404)
        self.assertEqual((await self.api("POST", REPORTS, {"analysis_id": str(uuid4())}))[0], 404)
        self.assertEqual((await self.api("GET", f"{REPORTS}/{uuid4()}/download"))[0], 404)
        with patch("app.modules.analysis.storage.list_runs", side_effect=sqlite3.OperationalError("private diagnostic")):
            code, error = await self.api("GET", ANALYSES)
        self.assertEqual(code, 503)
        self.assertNotIn("private diagnostic", error["detail"])
        with patch("app.modules.reports.get_run", side_effect=sqlite3.OperationalError("private diagnostic")):
            code, error = await self.api("POST", REPORTS, {"analysis_id": document_id})
        self.assertEqual(code, 503)
        self.assertNotIn("private diagnostic", error["detail"])
        self.assertEqual((await self.api("GET", REPORTS))[1], [])

    async def test_failed_run_cannot_be_exported(self):
        await self.activate("synthetic-a")
        identifier = await self.upload(pdf(PDF_TEXT), "fixture.pdf")
        with patch("app.modules.analysis.matching.evaluate", side_effect=RuntimeError("private diagnostic")):
            code, run = await self.api("POST", ANALYSES, {"document_ids": [identifier]})
        self.assertEqual((code, run["state"], run["results"]), (201, "failed", []))
        self.assertNotIn("private diagnostic", run["error"])
        self.assertEqual((await self.api("POST", REPORTS, {"analysis_id": run["id"]}))[0], 409)

    async def test_interrupted_write_is_reported_after_restart(self):
        await self.activate("synthetic-a")
        identifier = await self.upload(pdf(PDF_TEXT), "fixture.pdf")
        with patch("app.modules.analysis.storage.finish", side_effect=sqlite3.OperationalError("private diagnostic")):
            code, error = await self.api("POST", ANALYSES, {"document_ids": [identifier]})
        self.assertEqual(code, 503)
        self.assertNotIn("private diagnostic", error["detail"])
        self.app = create_app(self.db_path)
        async with self.app.router.lifespan_context(self.app):
            code, runs = await self.api("GET", ANALYSES)
            self.assertEqual((code, len(runs), runs[0]["state"], runs[0]["results"]), (200, 1, "failed", []))
            self.assertIn("прервалась", runs[0]["error"])

    async def test_html_snapshot_after_review_and_restart(self):
        await self.activate("synthetic-a")
        pdf_id = await self.upload(pdf(PDF_TEXT), "<source>.pdf")
        docx_id = await self.upload(docx(paragraph(SECTION_TITLE, heading=True) + paragraph(DOCX_TEXT)), "sample.docx")
        run = await self.launch(pdf_id, docx_id)
        url = f"{ANALYSES}/{run['id']}/results/SYN-01/review"
        review = {"comment": "Экспертная фикстура <пример>", "corrected_status": "соответствует",
                  "evidence_relations": {"0": "supports"}}
        self.assertEqual((await self.api("PUT", url, review))[0], 200)
        status, report = await self.api("POST", REPORTS, {"analysis_id": run["id"]})
        self.assertEqual(status, 201)
        download_path = f"{REPORTS}/{report['id']}/download"
        status, headers, body = await self.request("GET", download_path)
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"text/html; charset=utf-8")
        self.assertEqual(headers[b"content-disposition"], f'attachment; filename="{report["filename"]}"'.encode())
        self.assertEqual(headers[b"x-content-type-options"], b"nosniff")
        self.assertIn(b"default-src 'none'", headers[b"content-security-policy"])
        html = body.decode()
        for value in (
            "Предварительный отчёт о пробелах", run["id"], pdf_id, docx_id, "synthetic-a",
            "Учебный источник &lt;реквизит&gt;", "Учебный пункт &lt;A&gt;", "SYN-01",
            "Synthetic telemetry encryption &lt;policy&gt;", "&lt;source&gt;.pdf",
            "Страница 1", f"Раздел {SECTION_TITLE}", DOCX_TEXT,
            PDF_TEXT.replace("<", "&lt;").replace(">", "&gt;").replace(" & ", " &amp; "),
            "<dt>Текущий статус</dt><dd>соответствует</dd>",
            "<dt>Исходный статус</dt><dd>требуется проверка</dd>",
            "Экспертная фикстура &lt;пример&gt;", "недостаточно данных",
            run["results"][1]["explanation"], f"#documents?document={pdf_id}",
        ):
            self.assertIn(value, html)
        self.assertNotIn("<verification>", html)
        await self.api("PUT", url, {"comment": "Последующая правка"})
        self.app = create_app(self.db_path)
        async with self.app.router.lifespan_context(self.app):
            self.assertEqual((await self.request("GET", download_path))[2], body)
            self.assertEqual((await self.api("GET", REPORTS))[1], [report])
            self.assertEqual((await self.api("GET", "/api/v1/dashboard/summary"))[1],
                             {"documents": 2, "requirements": 2, "analyses": 1, "reports": 1})
