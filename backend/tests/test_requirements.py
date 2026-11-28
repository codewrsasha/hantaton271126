import hashlib
import json
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from app.main import create_app
from app.modules import documents, requirements
from app.modules.requirements import storage
from app.modules.requirements.models import MAX_BYTES

BASE = "/api/v1/requirements"


def package(revision="test-a", text="Синтетическая строка для теста."):
    return {
        "order_number": "117", "revision": revision, "revision_date": "2000-01-01",
        "obtained_on": "2000-01-02", "source": "Синтетическая фикстура",
        "requirements": [{"requirement_id": "T-1", "clause": "Тест 1", "requirement_text": text}],
    }


class RequirementsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.path = Path(self.enterContext(TemporaryDirectory())) / "test.db"
        self.app = create_app(self.path)
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))

    async def request(self, method, path, body=b"", *, client="127.0.0.1", marker=True, content=b"application/json"):
        sent = []
        headers = [(b"host", b"localhost"), (b"content-type", content)]
        if marker:
            headers.append((b"x-catalog-action", b"1"))

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            sent.append(message)

        await self.app({"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
                        "method": method, "http_version": "1.1", "scheme": "http",
                        "path": path, "query_string": b"", "headers": headers,
                        "server": ("localhost", 80), "client": (client, 1234)}, receive, send)
        return sent[0]["status"], json.loads(b"".join(m["body"] for m in sent[1:]))

    async def upload(self, data):
        return await self.request("POST", BASE + "/revisions", json.dumps(data).encode())

    async def change(self, rev, action, expected=200):
        status, data = await self.request("POST", f"{BASE}/revisions/{rev}/{action}")
        self.assertEqual(status, expected, data)
        return data

    async def test_existing_database_and_atomic_sql_failure(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""INSERT INTO documents VALUES ('test','a','a','pdf',1,'extracted',NULL,X'00')""")
            db.execute("""CREATE TRIGGER test_failure BEFORE INSERT ON requirement_entries
                          BEGIN SELECT RAISE(ABORT, 'test'); END""")
        requirements.initialize(self.path)
        requirements.initialize(self.path)
        self.assertEqual(documents.count_documents(self.path), 1)
        with self.assertLogs(storage.log, level="ERROR"):
            self.assertEqual((await self.upload(package()))[0], 503)
        self.assertEqual(await self.request("GET", BASE + "/revisions"), (200, []))

    async def test_lifecycle_and_citations(self):
        self.assertEqual(await self.request("GET", BASE + "/active"), (200, None))
        self.assertEqual(await self.request("GET", BASE), (200, []))
        first = package()
        first["requirements"].append({"requirement_id": "A", "clause": "Тест 2", "requirement_text": "Другой текст."})
        status, a = await self.upload(first)
        self.assertEqual((status, a["active"], a["state"], a["reviewed_at"], a["requirement_count"]),
                         (201, False, "draft", None, 2))
        self.assertEqual(a["sha256"], hashlib.sha256(json.dumps(first).encode()).hexdigest())
        self.assertEqual(await self.upload(first), (200, a))
        self.assertEqual((await self.upload(package()))[0], 409)
        await self.change("absent", "activate", 404)
        await self.change("test-a", "activate", 409)
        self.assertIsNotNone((await self.change("test-a", "publish"))["reviewed_at"])
        self.assertEqual(await self.request("GET", BASE), (200, []))
        await self.change("test-a", "activate")
        await self.change("test-a", "archive", 409)
        self.assertEqual((await self.request("GET", "/api/v1/dashboard/summary"))[1]["requirements"], 2)
        second = package("test-b", "Второй вариант.")
        self.assertEqual((await self.upload(second))[0], 201)
        await self.change("test-b", "publish")
        await self.change("test-b", "activate")
        await self.change("test-a", "archive")
        await self.change("test-a", "activate", 409)
        self.assertEqual((await self.request("GET", BASE + "/active"))[1]["revision"], "test-b")
        self.assertEqual((await self.request("GET", "/api/v1/dashboard/summary"))[1]["requirements"], 1)
        self.assertEqual((await self.request("GET", BASE))[1], [{
            "requirement_id": "T-1", "requirement_text": "Второй вариант.",
            "source_reference": {"order_number": "117", "revision": "test-b", "clause": "Тест 1"},
        }])
        old = (await self.request("GET", BASE + "/revisions/test-a/requirements"))[1]
        self.assertEqual([r["requirement_id"] for r in old], ["T-1", "A"])
        self.assertEqual(old[0]["requirement_text"], first["requirements"][0]["requirement_text"])
        self.assertEqual(len((await self.request("GET", BASE + "/revisions"))[1]), 2)
        await self.change("test-b", "deactivate")
        self.assertEqual(await self.request("GET", BASE), (200, []))

    async def test_invalid_packages(self):
        for key, value in (("order_number", "118"), ("revision", "../x"), ("source", " "),
                           ("revision_date", 123), ("obtained_on", "2000-02-30"), ("requirements", [])):
            with self.subTest(key=key):
                self.assertEqual((await self.upload(package() | {key: value}))[0], 422)
        for key in package():
            data = package()
            del data[key]
            self.assertEqual((await self.upload(data))[0], 422)
        for field, value in (("requirement_text", " "), ("requirement_text", 4), ("requirement_text", "\ud800")):
            data = package()
            data["requirements"][0][field] = value
            self.assertEqual((await self.upload(data))[0], 422)
        for override in ({"requirement_id": "X"}, {"clause": "X"}):
            data = package()
            data["requirements"].append(data["requirements"][0] | override)
            self.assertEqual((await self.upload(data))[0], 422)
        for raw in (b"[", b"\xff", b'{"revision":"a","revision":"b"}'):
            status, error = await self.request("POST", BASE + "/revisions", raw)
            self.assertEqual(status, 422)
            self.assertIsInstance(error["detail"], str)
        for kwargs, status in (({"client": "192.0.2.1"}, 403), ({"marker": False}, 403),
                               ({"content": b"text/plain"}, 415), ({"body": b"x" * (MAX_BYTES+1)}, 413)):
            self.assertEqual((await self.request("POST", BASE + "/revisions", **kwargs))[0], status)
        self.assertEqual(await self.request("GET", BASE + "/revisions"), (200, []))

    async def test_simultaneous_import(self):
        raw = json.dumps(package()).encode()
        model = requirements.parse_package(raw)
        digest = hashlib.sha256(raw).hexdigest()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: storage.save(self.path, model, digest)[1], range(2)))
        self.assertCountEqual(results, [True, False])
