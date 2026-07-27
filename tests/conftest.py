"""Shared pytest fixtures.

Tests use a fresh temporary SQLite file per test (rather than the real
``data/tracker.db``) so they never touch real task data and can run in
full isolation/parallel.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    """Point the app at a throwaway SQLite file for the duration of a test."""
    import src.database as database_module

    test_db_path = tmp_path / "test_tracker.db"
    monkeypatch.setattr(database_module, "DATABASE_PATH", test_db_path)
    database_module.initialize_database()
    yield test_db_path
