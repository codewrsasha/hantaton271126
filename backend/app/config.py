import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = ROOT / "frontend" / "dist"


def database_path() -> Path:
    load_dotenv(ROOT / ".env")
    return ROOT / os.environ.get("FSTEC_DATABASE_PATH", "data/inspector.sqlite3")


def document_max_bytes() -> int:
    load_dotenv(ROOT / ".env")
    try:
        limit = int(os.environ.get("FSTEC_DOCUMENT_MAX_BYTES", str(20 * 1024 * 1024)))
    except ValueError:
        limit = 0
    if not 1 <= limit <= 64 * 1024 * 1024:
        raise ValueError("FSTEC_DOCUMENT_MAX_BYTES must be between 1 and 67108864")
    return limit
