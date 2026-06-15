"""Root-level fixtures: prevent tests from touching the real database."""

import pytest


@pytest.fixture(autouse=True)
def _mock_db_file(monkeypatch):
    """All tests use an in-memory SQLite database."""
    from core.db import DB_FILE
    monkeypatch.setattr("core.db.DB_FILE", ":memory:")
