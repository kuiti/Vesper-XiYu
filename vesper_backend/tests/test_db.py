"""Tests for core.db basic CRUD operations.

Uses real SQLite with a temp file (conftest.py patches DB_FILE to ':memory:'
but we override with a temp file to avoid :memory: creating separate DBs per
connection).
"""

import os
import pytest
import sqlite3
import tempfile
from datetime import datetime


@pytest.fixture(autouse=True)
def _use_temp_db(monkeypatch, tmp_path):
    """Use a real temp file DB so all connections see the same tables."""
    import core.db
    db_file = str(tmp_path / "test_vesper.db")
    monkeypatch.setattr("core.db.DB_FILE", db_file)
    # Reset init flag so _ensure_db() runs on this temp DB
    core.db._db_initialized = False
    yield
    core.db._db_initialized = False


@pytest.fixture(autouse=True)
def _clear_config_cache():
    """Clear config cache between tests."""
    from core.db.config import _config_cache
    _config_cache.clear()
    yield
    _config_cache.clear()


# ─── config 表 CRUD ─────────────────────────────────────────────


class TestConfigCRUD:
    """set_config / get_config 基础读写。"""

    def test_set_and_get_string(self):
        from core.db import set_config, get_config
        set_config("test_key", "hello")
        assert get_config("test_key") == "hello"

    def test_set_and_get_int(self):
        from core.db import set_config, get_config
        set_config("count", 42)
        # 整数会被 JSON 序列化
        result = get_config("count")
        assert result == 42

    def test_set_and_get_bool(self):
        from core.db import set_config, get_config
        set_config("flag", True)
        assert get_config("flag") is True

    def test_set_and_get_dict(self):
        from core.db import set_config, get_config
        data = {"name": "夕语", "age": 18}
        set_config("character", data)
        result = get_config("character")
        assert result == data
        # 验证返回的是深拷贝（修改不影响缓存）
        result["name"] = "改了"
        assert get_config("character")["name"] == "夕语"

    def test_default_value_when_missing(self):
        from core.db import get_config
        assert get_config("nonexistent_key", "默认值") == "默认值"

    def test_default_none_when_missing(self):
        from core.db import get_config
        assert get_config("nonexistent_key") is None

    def test_overwrite_existing(self):
        from core.db import set_config, get_config
        set_config("k", "v1")
        set_config("k", "v2")
        assert get_config("k") == "v2"

    def test_set_and_get_list(self):
        from core.db import set_config, get_config
        data = [1, 2, 3]
        set_config("my_list", data)
        assert get_config("my_list") == data


# ─── chat_history CRUD ──────────────────────────────────────────


class TestChatHistory:
    """add_chat_message + 读取。"""

    def test_add_and_read(self):
        from core.db import add_chat_message, get_all_chat_messages
        add_chat_message("user", "你好")
        add_chat_message("assistant", "你好呀~")
        msgs = get_all_chat_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "你好"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "你好呀~"

    def test_custom_timestamp(self):
        from core.db import add_chat_message, get_all_chat_messages
        ts = "2026-01-01T00:00:00"
        add_chat_message("user", "测试时间戳", timestamp=ts)
        msgs = get_all_chat_messages()
        assert msgs[0]["timestamp"] == ts

    def test_returns_id(self):
        from core.db import add_chat_message
        msg_id = add_chat_message("user", "测试ID")
        assert isinstance(msg_id, int)
        assert msg_id > 0

    def test_get_recent_messages(self):
        from core.db import add_chat_message, get_recent_chat_messages
        for i in range(5):
            add_chat_message("user", f"消息{i}")
        recent = get_recent_chat_messages(limit=3)
        assert len(recent) == 3
        # 应该是时间正序（最近的在后）
        assert recent[0]["content"] == "消息2"
        assert recent[2]["content"] == "消息4"


# ─── 表存在性 ───────────────────────────────────────────────────


class TestTableExistence:
    """验证建表是否成功。"""

    @pytest.fixture
    def _tables(self):
        """获取所有表名列表。"""
        from core.db import get_conn
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            return {row["name"] for row in cursor.fetchall()}

    def test_config_table(self, _tables):
        assert "config" in _tables

    def test_chat_history_table(self, _tables):
        assert "chat_history" in _tables

    def test_reminders_table(self, _tables):
        assert "reminders" in _tables

    def test_memory_table(self, _tables):
        assert "memory" in _tables

    def test_user_profile_table(self, _tables):
        assert "user_profile" in _tables

    def test_tiered_summary_table(self, _tables):
        assert "tiered_summary" in _tables

    def test_todos_table(self, _tables):
        assert "todos" in _tables

    def test_notes_table(self, _tables):
        assert "notes" in _tables

    def test_habits_table(self, _tables):
        assert "habits" in _tables

    def test_presets_table(self, _tables):
        assert "presets" in _tables

    def test_documents_table(self, _tables):
        assert "documents" in _tables

    def test_emotion_daily_table(self, _tables):
        assert "emotion_daily" in _tables

    def test_relationship_table(self, _tables):
        assert "relationship" in _tables

    def test_demand_patterns_table(self, _tables):
        assert "demand_patterns" in _tables

    def test_goal_tracking_table(self, _tables):
        assert "goal_tracking" in _tables

    def test_sentence_index_table(self, _tables):
        assert "sentence_index" in _tables

    def test_memory_importance_table(self, _tables):
        assert "memory_importance" in _tables

    def test_knowledge_graph_table(self, _tables):
        assert "knowledge_graph" in _tables

    def test_schedule_table(self, _tables):
        assert "schedule" in _tables

    def test_achievements_table(self, _tables):
        assert "achievements" in _tables

    def test_ai_diary_table(self, _tables):
        assert "ai_diary" in _tables

    def test_characters_table(self, _tables):
        assert "characters_v2" in _tables

    def test_entities_table(self, _tables):
        assert "entities" in _tables

    def test_favorites_table(self, _tables):
        assert "favorites" in _tables

    def test_fts_table(self, _tables):
        """FTS5 虚拟表也应存在。"""
        from core.db import get_conn
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_fts'")
            assert cursor.fetchone() is not None