"""Browser integration checks against a temporary database and the built frontend."""
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import ProxyHandler, Request, build_opener

import uvicorn

from app.config import FRONTEND_DIST
from app.main import create_app
from tests.test_requirements import package


def browser_path():
    for candidate in (os.environ.get("CHROMIUM_PATH"), shutil.which("chromium"), shutil.which("google-chrome"),
                      Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
                      Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe"):
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return None


@unittest.skipUnless(browser_path() and (FRONTEND_DIST / "index.html").is_file(),
                     "Requires a built frontend and a local Chromium browser")
class CatalogBrowserTests(unittest.TestCase):
    def test_catalog_states_and_historical_link(self):
        with TemporaryDirectory() as directory, socket.socket() as listener:
            path = Path(directory)
            listener.bind(("127.0.0.1", 0))
            origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
            server = uvicorn.Server(uvicorn.Config(create_app(path / "ui.db"), log_level="error"))
            thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            try:
                for _ in range(200):
                    if server.started:
                        break
                    time.sleep(.025)
                self.assertTrue(server.started)

                def page(fragment=""):
                    result = subprocess.run([
                        browser_path(), "--headless", "--disable-gpu", "--disable-background-networking",
                        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                        "--user-data-dir=" + str(path / "profile"), "--virtual-time-budget=5000",
                        "--dump-dom", origin + "/#requirements" + fragment,
                    ], capture_output=True, timeout=45, check=True)
                    return result.stdout.decode("utf-8")

                self.assertIn("База требований пока пуста", page())
                client = build_opener(ProxyHandler({}))

                def post(route, body=b""):
                    req = Request(origin + "/api/v1/requirements/revisions" + route, data=body,
                                  headers={"X-Catalog-Action": "1", "Content-Type": "application/json"})
                    with client.open(req, timeout=5) as reply:
                        return json.load(reply)

                post("", json.dumps(package()).encode())
                post("", json.dumps(package("test-b", "Синтетический вариант Б.")).encode())
                post("/test-b/publish")
                post("/test-b/activate")
                html = page()
                self.assertIn("Синтетический вариант Б.", html)
                self.assertIn("test-a", html)
                self.assertIn("test-b", html)
                old = page("?requirement=T-1&revision=test-a&clause=%D0%A2%D0%B5%D1%81%D1%82+1")
                self.assertIn("Синтетическая строка для теста.", old)
                self.assertNotIn("Синтетический вариант Б.", old)
                self.assertIn("Ссылка неполна", page("?requirement=T-1"))
                self.assertIn("Требование по этой ссылке не найдено", page("?requirement=T-1&revision=test-a&clause=X"))
                # The server keeps serving the UI after loss of its disposable database.
                (path / "ui.db").unlink()
                self.assertIn("Не удалось получить данные", page())
            finally:
                server.should_exit = True
                thread.join(timeout=10)
