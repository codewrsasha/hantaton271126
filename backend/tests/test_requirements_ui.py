"""Browser integration checks against a temporary database and the built frontend."""
import os
import shutil
import socket
import subprocess
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn

from app.config import FRONTEND_DIST
from app.main import create_app


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

                def page(fragment="", route="#analysis?catalog=1"):
                    result = subprocess.run([
                        browser_path(), "--headless", "--disable-gpu", "--disable-background-networking",
                        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                        "--user-data-dir=" + str(path / "profile"), "--virtual-time-budget=5000",
                        "--dump-dom", origin + "/" + route + fragment,
                    ], capture_output=True, timeout=45, check=True)
                    return result.stdout.decode("utf-8")

                home = page(route="#chat")
                self.assertIn("История чатов", home)
                self.assertIn("Добавить файл", home)
                self.assertIn('aria-label="Сообщение"', home)
                catalog = page(route="#requirements")
                self.assertIn('id="source-title"', catalog)
                self.assertIn("FSTEC117-MAIN-001", catalog)
                self.assertIn("FSTEC117-APP-011", catalog)
                self.assertNotIn("Добавить требования", catalog)
                self.assertNotIn("Архивировать", catalog)
                deep = page("?requirement=FSTEC117-MAIN-001&revision=117-2026-05-08", route="#requirements")
                self.assertIn('aria-expanded="true"', deep)
                self.assertIn('class="clause-text"', deep)
                self.assertIn("Требование по этой ссылке не найдено", page("?requirement=unknown", route="#requirements"))
            finally:
                server.should_exit = True
                thread.join(timeout=10)
