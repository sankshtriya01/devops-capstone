"""Small database layer.

PostgreSQL is used in Docker and Kubernetes (set DATABASE_URL).
SQLite is used for unit tests and quick local runs (the default, in memory).
SQL in this project uses "?" placeholders; they are converted for PostgreSQL.
"""
import contextlib
import os
import sqlite3
import threading
import time

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///:memory:")

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        done INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )""",
]

_sqlite_lock = threading.Lock()
_memory_conn = None


def is_postgres():
    return DATABASE_URL.startswith(("postgres://", "postgresql://"))


def _connect():
    global _memory_conn
    if is_postgres():
        import psycopg2  # imported here so tests do not need it
        return psycopg2.connect(DATABASE_URL, connect_timeout=5)
    path = DATABASE_URL.replace("sqlite:///", "", 1)
    if path == ":memory:":
        if _memory_conn is None:
            _memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
        return _memory_conn
    return sqlite3.connect(path)


def run(sql, params=(), fetch="none"):
    """Run one SQL statement. fetch is 'none', 'one' or 'all'."""
    guard = contextlib.nullcontext() if is_postgres() else _sqlite_lock
    with guard:
        conn = _connect()
        try:
            cur = conn.cursor()
            cur.execute(sql.replace("?", "%s") if is_postgres() else sql, params)
            result = None
            if fetch == "all":
                result = cur.fetchall()
            elif fetch == "one":
                result = cur.fetchone()
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            if conn is not _memory_conn:
                conn.close()


def init(retries=30, delay=2):
    """Create the tables. Retries because the database may still be starting."""
    for attempt in range(retries):
        try:
            for statement in SCHEMA:
                run(statement)
            return
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def reset_for_tests():
    run("DELETE FROM tasks")
    run("DELETE FROM users")
