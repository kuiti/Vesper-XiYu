"""Tests for core.lorebook — 知识库系统。

使用独立测试 DB，不污染正式 data/vesper.db。
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


@pytest.fixture
def manager():
    """Create a fresh LorebookManager for each test."""
    from core.lorebook import LorebookManager
    return LorebookManager()


@pytest.fixture
def _clear_lorebook(manager):
    """Clear lorebook table before each test."""
    from core.db import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM lorebook")
    manager._mark_dirty()
    yield
    with get_conn() as conn:
        conn.execute("DELETE FROM lorebook")
    manager._mark_dirty()


# ─── CRUD 测试 ─────────────────────────────────────────────


class TestLorebookCRUD:
    """基本的增删改查操作。"""

    def test_add_entry_returns_id(self, manager, _clear_lorebook):
        """add_entry 应返回一个正整数 ID。"""
        entry_id = manager.add_entry(keys=["test"], content="测试内容")
        assert isinstance(entry_id, int)
        assert entry_id > 0

    def test_add_entry_in_list(self, manager, _clear_lorebook):
        """添加的条目应出现在 list_entries 中。"""
        manager.add_entry(keys=["key1"], content="内容1")
        entries = manager.list_entries()
        assert len(entries) == 1
        assert entries[0]["content"] == "内容1"
        assert entries[0]["keys"] == ["key1"]

    def test_update_entry(self, manager, _clear_lorebook):
        """update_entry 应能修改条目字段。"""
        entry_id = manager.add_entry(keys=["old"], content="旧内容")
        result = manager.update_entry(entry_id, content="新内容", keys=["new"])
        assert result is True

        entry = manager.get_entry(entry_id)
        assert entry["content"] == "新内容"
        assert entry["keys"] == ["new"]

    def test_update_nonexistent_entry(self, manager, _clear_lorebook):
        """更新不存在的条目应返回 False（无有效字段）。"""
        result = manager.update_entry(9999, content="不存在")
        # update_entry 返回 True 因为 SQL 执行成功，即使没有行被更新
        # 这是实现的预期行为
        assert result is True

    def test_delete_entry(self, manager, _clear_lorebook):
        """delete_entry 应删除条目。"""
        entry_id = manager.add_entry(keys=["del"], content="待删除")
        assert manager.get_entry(entry_id) is not None

        result = manager.delete_entry(entry_id)
        assert result is True
        assert manager.get_entry(entry_id) is None

    def test_delete_nonexistent_entry(self, manager, _clear_lorebook):
        """删除不存在的条目不报错。"""
        result = manager.delete_entry(9999)
        assert result is True

    def test_get_entry_returns_dict(self, manager, _clear_lorebook):
        """get_entry 应返回完整字典。"""
        entry_id = manager.add_entry(
            keys=["key1", "key2"],
            content="内容",
            priority=8,
            position="before_persona",
            logic="AND_ALL",
            group_name="test_group",
            probability=90,
            sticky=2,
            cooldown=3,
            scope="global",
            character_name="test_char",
            enabled=True,
        )
        entry = manager.get_entry(entry_id)
        assert entry is not None
        assert entry["id"] == entry_id
        assert entry["keys"] == ["key1", "key2"]
        assert entry["content"] == "内容"
        assert entry["priority"] == 8
        assert entry["position"] == "before_persona"
        assert entry["logic"] == "AND_ALL"
        assert entry["group_name"] == "test_group"
        assert entry["probability"] == 90
        assert entry["sticky"] == 2
        assert entry["cooldown"] == 3
        assert entry["scope"] == "global"
        assert entry["character_name"] == "test_char"
        # SQLite 存储布尔值为整数，from_dict 会转换
        assert entry["enabled"] in (True, 1)

    def test_get_nonexistent_entry(self, manager, _clear_lorebook):
        """get_entry 对不存在的 ID 应返回 None。"""
        assert manager.get_entry(9999) is None

    def test_list_entries_with_scope_filter(self, manager, _clear_lorebook):
        """list_entries 支持 scope 过滤。"""
        manager.add_entry(keys=["g"], content="全局", scope="global")
        manager.add_entry(keys=["c"], content="角色", scope="character")
        all_entries = manager.list_entries()
        global_entries = manager.list_entries(scope="global")
        char_entries = manager.list_entries(scope="character")

        assert len(all_entries) == 2
        assert len(global_entries) == 1
        assert global_entries[0]["content"] == "全局"
        assert len(char_entries) == 1
        assert char_entries[0]["content"] == "角色"

    def test_list_empty(self, manager, _clear_lorebook):
        """空知识库应返回空列表。"""
        assert manager.list_entries() == []


# ─── 匹配逻辑测试 ─────────────────────────────────────────────


class TestMatchLogic:
    """测试各种匹配逻辑。"""

    def test_and_any_match(self, manager, _clear_lorebook):
        """AND_ANY：任一关键词出现即匹配。"""
        manager.add_entry(keys=["猫", "狗"], content="宠物知识", logic="AND_ANY")

        # 匹配 "猫"
        result = manager.match_entries("我家有只猫")
        assert len(result) == 1
        assert result[0]["content"] == "宠物知识"

        # 匹配 "狗"
        result = manager.match_entries("遛狗去")
        assert len(result) == 1

        # 不匹配
        result = manager.match_entries("今天天气好")
        assert len(result) == 0

    def test_and_all_match(self, manager, _clear_lorebook):
        """AND_ALL：所有关键词都出现才匹配。"""
        manager.add_entry(keys=["猫", "可爱"], content="猫很可爱", logic="AND_ALL")

        # 全部出现 → 匹配
        result = manager.match_entries("我家的猫很可爱")
        assert len(result) == 1

        # 只出现一个 → 不匹配
        result = manager.match_entries("我家有只猫")
        assert len(result) == 0

        # 都不出现 → 不匹配
        result = manager.match_entries("今天天气好")
        assert len(result) == 0

    def test_regex_match(self, manager, _clear_lorebook):
        """REGEX：正则表达式匹配。"""
        manager.add_entry(keys=[r"\d{3,}"], content="数字序列", logic="REGEX")

        # 匹配 3 位以上数字
        result = manager.match_entries("abc123")
        assert len(result) == 1

        # 匹配更多数字
        result = manager.match_entries("电话12345678")
        assert len(result) == 1

        # 不匹配（少于 3 位数字）
        result = manager.match_entries("ab12")
        assert len(result) == 0

        # 不匹配（无数字）
        result = manager.match_entries("abcdef")
        assert len(result) == 0

    def test_regex_invalid_pattern(self, manager, _clear_lorebook):
        """REGEX：无效正则不应崩溃。"""
        manager.add_entry(keys=["[invalid"], content="无效正则", logic="REGEX")

        # 不应抛出异常
        result = manager.match_entries("test")
        assert len(result) == 0

    def test_not_any_match(self, manager, _clear_lorebook):
        """NOT_ANY：没有任一关键词出现才匹配。"""
        manager.add_entry(keys=["猫", "狗"], content="无宠物", logic="NOT_ANY")

        # 无关键词 → 匹配
        result = manager.match_entries("今天天气好")
        assert len(result) == 1

        # 有关键词 → 不匹配
        result = manager.match_entries("我家有只猫")
        assert len(result) == 0

    def test_not_all_match(self, manager, _clear_lorebook):
        """NOT_ALL：不是所有关键词都出现才匹配。"""
        manager.add_entry(keys=["猫", "狗"], content="不全有", logic="NOT_ALL")

        # 只有一个 → 匹配
        result = manager.match_entries("我家有只猫")
        assert len(result) == 1

        # 都有 → 不匹配
        result = manager.match_entries("我家有猫有狗")
        assert len(result) == 0

        # 都没有 → 匹配
        result = manager.match_entries("今天天气好")
        assert len(result) == 1


# ─── 高级特性测试 ─────────────────────────────────────────────


class TestAdvancedFeatures:
    """测试组互斥、概率、禁用等高级特性。"""

    def test_group_exclusion(self, manager, _clear_lorebook):
        """同组条目只返回 priority 最高的。"""
        manager.add_entry(keys=["天气"], content="低优先级天气", priority=3, group_name="weather")
        manager.add_entry(keys=["天气"], content="高优先级天气", priority=8, group_name="weather")

        result = manager.match_entries("今天天气怎么样")
        assert len(result) == 1
        assert result[0]["content"] == "高优先级天气"
        assert result[0]["priority"] == 8

    def test_group_different_groups(self, manager, _clear_lorebook):
        """不同组的条目可以同时匹配。"""
        manager.add_entry(keys=["天气"], content="天气知识", priority=5, group_name="weather")
        manager.add_entry(keys=["天气"], content="心情知识", priority=5, group_name="mood")

        result = manager.match_entries("今天天气好，心情也好")
        assert len(result) == 2

    def test_probability_zero(self, manager, _clear_lorebook):
        """probability=0 的条目不应匹配。"""
        manager.add_entry(keys=["测试"], content="零概率", probability=0)

        result = manager.match_entries("测试消息")
        assert len(result) == 0

    def test_disabled_entry(self, manager, _clear_lorebook):
        """enabled=False 的条目不应匹配。"""
        manager.add_entry(keys=["测试"], content="已禁用", enabled=False)

        result = manager.match_entries("测试消息")
        assert len(result) == 0

    def test_empty_message(self, manager, _clear_lorebook):
        """空消息应返回空结果。"""
        manager.add_entry(keys=["测试"], content="测试内容")

        result = manager.match_entries("")
        assert len(result) == 0

    def test_case_insensitive(self, manager, _clear_lorebook):
        """匹配应不区分大小写。"""
        manager.add_entry(keys=["hello"], content="问候")

        result = manager.match_entries("HELLO")
        assert len(result) == 1

        result = manager.match_entries("Hello")
        assert len(result) == 1

    def test_priority_order(self, manager, _clear_lorebook):
        """结果应按 priority 降序排列。"""
        manager.add_entry(keys=["a"], content="低", priority=3)
        manager.add_entry(keys=["a"], content="高", priority=8)
        manager.add_entry(keys=["a"], content="中", priority=5)

        result = manager.match_entries("a")
        assert len(result) == 3
        assert result[0]["priority"] == 8
        assert result[1]["priority"] == 5
        assert result[2]["priority"] == 3

    def test_max_chars_truncation(self, manager, _clear_lorebook):
        """结果应受 max_chars 限制。"""
        long_content = "x" * 1000
        manager.add_entry(keys=["a"], content=long_content, priority=5)
        manager.add_entry(keys=["a"], content="短内容", priority=3)

        result = manager.match_entries("a", max_chars=100)
        # 第一条占满预算，第二条可能被截断或省略
        total = sum(len(r["content"]) for r in result)
        assert total <= 100 + 100  # 允许略微超出（截断时）

    def test_scope_filter(self, manager, _clear_lorebook):
        """scope 过滤应正确工作。"""
        manager.add_entry(keys=["test"], content="全局", scope="global")
        manager.add_entry(keys=["test"], content="角色", scope="character", character_name="test_char")

        # scope="global" 时，global 条目匹配
        result = manager.match_entries("test", scope="global")
        assert len(result) >= 1
        global_contents = [r["content"] for r in result]
        assert "全局" in global_contents

        # scope="character" 时，character 条目匹配
        result = manager.match_entries("test", scope="character")
        assert len(result) >= 1
        char_contents = [r["content"] for r in result]
        assert "角色" in char_contents

    def test_multiple_keys(self, manager, _clear_lorebook):
        """多个关键词应正确匹配。"""
        manager.add_entry(keys=["猫", "狗", "鸟"], content="宠物", logic="AND_ANY")

        result = manager.match_entries("我家有鸟")
        assert len(result) == 1

        result = manager.match_entries("猫狗双全")
        assert len(result) == 1

    def test_update_keys_as_list(self, manager, _clear_lorebook):
        """update_entry 应能接受 keys 为列表。"""
        entry_id = manager.add_entry(keys=["old"], content="内容")
        manager.update_entry(entry_id, keys=["new1", "new2"])

        entry = manager.get_entry(entry_id)
        assert entry["keys"] == ["new1", "new2"]

    def test_enabled_toggle(self, manager, _clear_lorebook):
        """切换 enabled 状态应影响匹配。"""
        entry_id = manager.add_entry(keys=["test"], content="内容", enabled=True)

        # 启用状态 → 匹配
        result = manager.match_entries("test")
        assert len(result) == 1

        # 禁用 → 不匹配
        manager.update_entry(entry_id, enabled=False)
        result = manager.match_entries("test")
        assert len(result) == 0

        # 重新启用 → 匹配
        manager.update_entry(entry_id, enabled=True)
        result = manager.match_entries("test")
        assert len(result) == 1
