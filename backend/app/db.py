import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path


def check_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA user_version").fetchone()


@contextmanager
def transaction(path: Path) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection
