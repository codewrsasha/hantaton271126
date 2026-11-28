import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.main import create_app
from app.modules import requirements
from app.modules.requirements import storage
from app.modules.requirements.models import parse_package

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
        body = b"".join(m["body"] for m in sent[1:])
        return sent[0]["status"], json.loads(body) if body else None

    async def test_exact_bundled_source(self):
        raw = requirements.SOURCE.read_bytes()
        source = json.loads(raw.decode("utf-8-sig"))
        status, meta = await self.request("GET", BASE + "/active")
        self.assertEqual(status, 200)
        self.assertEqual(meta["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(meta["sha256"], "d994cdbec765afb9eef7c804943055f79eaecdbd2b0f4ea334a817731b7b589c")
        self.assertEqual((meta["requirement_count"], meta["revision"]), (84, source["revision"]))
        self.assertEqual(await self.request("GET", BASE + "/revisions"), (200, [meta]))
        expected = [{"requirement_id": row["requirement_id"], "requirement_text": row["requirement_text"],
                     "source_reference": {"order_number": "117", "revision": meta["revision"], "clause": row["clause"]}}
                    for row in source["requirements"]]
        self.assertEqual(await self.request("GET", BASE), (200, expected))
        self.assertEqual(await self.request("GET", BASE + "/revisions/" + meta["revision"] + "/requirements"), (200, expected))

    async def test_legacy_database_never_changes_source(self):
        storage.initialize(self.path)
        raw = json.dumps(package()).encode()
        storage.save(self.path, parse_package(raw), hashlib.sha256(raw).hexdigest())
        storage.transition(self.path, "test-a", "publish")
        storage.transition(self.path, "test-a", "activate")
        self.assertEqual((await self.request("GET", BASE + "/revisions/test-a/requirements"))[0], 404)
        self.assertEqual(len((await self.request("GET", BASE))[1]), 84)
        self.assertEqual((await self.request("GET", "/api/v1/dashboard/summary"))[1]["requirements"], 84)
        self.assertEqual(storage.active_revision(self.path).revision, "test-a")

    async def test_no_catalog_mutation_routes(self):
        schema = self.app.openapi()["paths"]
        routes = [methods for path, methods in schema.items() if path.startswith(BASE)]
        self.assertEqual(len(routes), 4)
        self.assertTrue(all(set(methods) == {"get"} for methods in routes))
        for path in ("/revisions", "/convert", "/revisions/test-a/publish", "/revisions/test-a/activate",
                     "/revisions/test-a/archive", "/revisions/test-a/deactivate"):
            self.assertIn((await self.request("POST", BASE + path))[0], (404, 405))
        self.assertIn((await self.request("DELETE", BASE + "/revisions/test-a"))[0], (404, 405))
