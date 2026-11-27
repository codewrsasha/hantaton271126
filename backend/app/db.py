import sqlite3
from contextlib import closing
from pathlib import Path


def check_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA user_version").fetchone()
