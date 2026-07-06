"""Root-level fixtures: prevent tests from touching the real database."""

import pytest
import sqlite3


@pytest.fixture(autouse=True)
def _mock_db_file(monkeypatch):
    """All tests use an in-memory SQLite database."""
    monkeypatch.setattr("core.db.DB_FILE", ":memory:")

    # Mock get_chat_conn: cache per character_id within each test
    _chat_conns = {}

    def _mock_get_chat_conn(character_id=0):
        if character_id not in _chat_conns:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            from core.db import _init_chat_schema
            _init_chat_schema(conn)
            _chat_conns[character_id] = conn
        return _chat_conns[character_id]

    monkeypatch.setattr("core.db.get_chat_conn", _mock_get_chat_conn)

    # Mock get_char_profile_conn: cache per character_id within each test
    _profile_conns = {}

    def _mock_get_char_profile_conn(character_id):
        if character_id not in _profile_conns:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            from core.db import _init_profile_schema
            _init_profile_schema(conn)
            _profile_conns[character_id] = conn
        return _profile_conns[character_id]

    monkeypatch.setattr("core.db.get_char_profile_conn", _mock_get_char_profile_conn)
