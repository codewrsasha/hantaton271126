import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = ROOT / "frontend" / "dist"


def database_path() -> Path:
    load_dotenv(ROOT / ".env")
    return ROOT / os.environ.get("FSTEC_DATABASE_PATH", "data/inspector.sqlite3")
