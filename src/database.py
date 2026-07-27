"""SQLite connection handling and schema initialization.

The whole application talks to SQLite through :func:`get_connection`, which
returns a context-managed connection with ``row_factory`` set to
``sqlite3.Row`` so calling code can access columns by name. This keeps
connection lifecycle handling (commit/rollback/close) in one place.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from src.config import DATABASE_PATH
from src.utils import get_logger

logger = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    category        TEXT DEFAULT 'Other',
    priority        TEXT DEFAULT 'Medium',
    status          TEXT DEFAULT 'pending',
    due_date        TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS daily_snapshots (
    date            TEXT PRIMARY KEY,
    completed_tasks INTEGER NOT NULL,
    total_tasks     INTEGER NOT NULL,
    completion_pct  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS email_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at         TEXT NOT NULL,
    email_type      TEXT NOT NULL,
    recipient       TEXT NOT NULL,
    success         INTEGER NOT NULL,
    detail          TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
"""


def initialize_database() -> None:
    """Create all required tables/indexes if they do not already exist.

    Safe to call on every app startup - all statements use
    ``IF NOT EXISTS`` so this never destroys existing data.
    """
    with get_connection() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.info("Database initialized at %s", DATABASE_PATH)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection with sane defaults, closing it afterward.

    Foreign keys are enabled and ``row_factory`` is set to ``sqlite3.Row``
    so downstream code can do ``row["title"]`` instead of relying on
    positional tuple indices.

    Yields:
        sqlite3.Connection: An open connection to the tracker database.
    """
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    except sqlite3.Error:
        conn.rollback()
        logger.exception("Database error - transaction rolled back")
        raise
    finally:
        conn.close()
