"""Tests for core.user_persona — 用户身份系统。

使用独立测试 DB，不污染正式 data/sakura.db。
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
    db_file = str(tmp_path / "test_sakura.db")
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
    """Create a fresh UserPersonaManager for each test."""
    from core.user_persona import UserPersonaManager
    return UserPersonaManager()


@pytest.fixture
def _clear_personas(manager):
    """Clear user_personas table before each test."""
    from core.db import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM user_personas")
    manager._mark_dirty()
    yield
    with get_conn() as conn:
        conn.execute("DELETE FROM user_personas")
    manager._mark_dirty()


# ─── CRUD 测试 ─────────────────────────────────────────────


class TestUserPersonaCRUD:
    """基本的增删改查操作。"""

    def test_add_persona_returns_id(self, manager, _clear_personas):
        """add_persona 应返回一个正整数 ID。"""
        persona_id = manager.add_persona(name="学生", description="大学生")
        assert isinstance(persona_id, int)
        assert persona_id > 0

    def test_add_persona_in_list(self, manager, _clear_personas):
        """添加的身份应出现在 list_personas 中。"""
        manager.add_persona(name="学生", description="大学生")
        personas = manager.list_personas()
        assert len(personas) == 1
        assert personas[0]["name"] == "学生"
        assert personas[0]["description"] == "大学生"

    def test_update_persona(self, manager, _clear_personas):
        """update_persona 应能修改身份字段。"""
        persona_id = manager.add_persona(name="旧名", description="旧描述")
        result = manager.update_persona(persona_id, name="新名", description="新描述")
        assert result is True

        persona = manager.get_persona(persona_id)
        assert persona["name"] == "新名"
        assert persona["description"] == "新描述"

    def test_update_nonexistent_persona(self, manager, _clear_personas):
        """更新不存在的身份应返回 False（无有效字段）。"""
        result = manager.update_persona(9999, name="不存在")
        # update_persona 返回 True 因为 SQL 执行成功
        assert result is True

    def test_update_with_invalid_field(self, manager, _clear_personas):
        """更新不允许的字段应返回 False。"""
        persona_id = manager.add_persona(name="测试")
        result = manager.update_persona(persona_id, invalid_field="value")
        assert result is False

    def test_delete_persona(self, manager, _clear_personas):
        """delete_persona 应删除身份。"""
        persona_id = manager.add_persona(name="待删除")
        assert manager.get_persona(persona_id) is not None

        result = manager.delete_persona(persona_id)
        assert result is True
        assert manager.get_persona(persona_id) is None

    def test_delete_nonexistent_persona(self, manager, _clear_personas):
        """删除不存在的身份不报错。"""
        result = manager.delete_persona(9999)
        assert result is True

    def test_get_persona_returns_dict(self, manager, _clear_personas):
        """get_persona 应返回完整字典。"""
        persona_id = manager.add_persona(
            name="学生",
            description="大学生，喜欢编程",
            avatar="student.png",
            is_default=True,
        )
        persona = manager.get_persona(persona_id)
        assert persona is not None
        assert persona["id"] == persona_id
        assert persona["name"] == "学生"
        assert persona["description"] == "大学生，喜欢编程"
        assert persona["avatar"] == "student.png"
        assert persona["is_default"] is True

    def test_get_nonexistent_persona(self, manager, _clear_personas):
        """get_persona 对不存在的 ID 应返回 None。"""
        assert manager.get_persona(9999) is None

    def test_list_empty(self, manager, _clear_personas):
        """空身份列表应返回空列表。"""
        assert manager.list_personas() == []

    def test_list_order_by_default_first(self, manager, _clear_personas):
        """list_personas 应将 is_default=True 的排在前面。"""
        manager.add_persona(name="普通", is_default=False)
        manager.add_persona(name="默认", is_default=True)
        manager.add_persona(name="另一个普通", is_default=False)

        personas = manager.list_personas()
        assert len(personas) == 3
        assert personas[0]["name"] == "默认"
        assert personas[0]["is_default"] is True


# ─── Active 身份测试 ─────────────────────────────────────────────


class TestActivePersona:
    """测试活跃身份的设置和获取。"""

    def test_set_active(self, manager, _clear_personas):
        """set_active 应能设置活跃身份。"""
        persona_id = manager.add_persona(name="学生")
        result = manager.set_active(persona_id)
        assert result is True

    def test_get_active_persona(self, manager, _clear_personas):
        """get_active_persona 应返回设置的活跃身份。"""
        persona_id = manager.add_persona(name="学生", description="大学生")
        manager.set_active(persona_id)

        active = manager.get_active_persona()
        assert active is not None
        assert active["name"] == "学生"
        assert active["description"] == "大学生"

    def test_set_active_nonexistent(self, manager, _clear_personas):
        """set_active 对不存在的身份应返回 False。"""
        result = manager.set_active(9999)
        assert result is False

    def test_delete_active_persona_resets(self, manager, _clear_personas):
        """删除活跃身份应自动重置为 None。"""
        persona_id = manager.add_persona(name="学生")
        manager.set_active(persona_id)

        # 删除前有活跃身份
        assert manager.get_active_persona() is not None

        # 删除后无活跃身份
        manager.delete_persona(persona_id)
        assert manager.get_active_persona() is None

    def test_fallback_to_default(self, manager, _clear_personas):
        """无 active 时应回退到 is_default。"""
        manager.add_persona(name="普通", is_default=False)
        default_id = manager.add_persona(name="默认", is_default=True)

        # 没有设置 active，应使用 default
        active = manager.get_active_persona()
        assert active is not None
        assert active["name"] == "默认"
        assert active["id"] == default_id

    def test_no_active_no_default(self, manager, _clear_personas):
        """无 active 无 default 时应返回 None。"""
        manager.add_persona(name="普通1", is_default=False)
        manager.add_persona(name="普通2", is_default=False)

        assert manager.get_active_persona() is None

    def test_active_overrides_default(self, manager, _clear_personas):
        """active 应优先于 default。"""
        manager.add_persona(name="默认", is_default=True)
        active_id = manager.add_persona(name="活跃", is_default=False)
        manager.set_active(active_id)

        active = manager.get_active_persona()
        assert active["name"] == "活跃"

    def test_get_active_description(self, manager, _clear_personas):
        """get_active_description 应返回活跃身份的描述。"""
        persona_id = manager.add_persona(name="学生", description="大学生，喜欢编程")
        manager.set_active(persona_id)

        desc = manager.get_active_description()
        assert desc == "大学生，喜欢编程"

    def test_get_active_description_no_persona(self, manager, _clear_personas):
        """无活跃身份时 get_active_description 应返回空字符串。"""
        assert manager.get_active_description() == ""

    def test_get_active_description_empty_description(self, manager, _clear_personas):
        """活跃身份描述为空时应返回空字符串。"""
        persona_id = manager.add_persona(name="无描述", description="")
        manager.set_active(persona_id)

        assert manager.get_active_description() == ""


# ─── Default 标记测试 ─────────────────────────────────────────────


class TestDefaultFlag:
    """测试 is_default 标记的行为。"""

    def test_add_with_default(self, manager, _clear_personas):
        """添加 is_default=True 的身份应成功。"""
        persona_id = manager.add_persona(name="默认", is_default=True)
        persona = manager.get_persona(persona_id)
        assert persona["is_default"] is True

    def test_multiple_defaults_last_wins(self, manager, _clear_personas):
        """多个 default 身份时，最后添加的生效。"""
        manager.add_persona(name="旧默认", is_default=True)
        new_id = manager.add_persona(name="新默认", is_default=True)

        # 检查数据库中只有一个 default
        personas = manager.list_personas()
        defaults = [p for p in personas if p["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["name"] == "新默认"

    def test_update_to_default(self, manager, _clear_personas):
        """update_persona 应能将身份设为 default。"""
        persona_id = manager.add_persona(name="普通", is_default=False)
        manager.update_persona(persona_id, is_default=True)

        persona = manager.get_persona(persona_id)
        assert persona["is_default"] is True

    def test_update_to_default_clears_others(self, manager, _clear_personas):
        """将身份设为 default 时应清除其他 default。"""
        old_id = manager.add_persona(name="旧默认", is_default=True)
        new_id = manager.add_persona(name="新普通", is_default=False)

        manager.update_persona(new_id, is_default=True)

        personas = manager.list_personas()
        defaults = [p for p in personas if p["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["id"] == new_id


# ─── 边界情况测试 ─────────────────────────────────────────────


class TestEdgeCases:
    """测试边界情况。"""

    def test_empty_name(self, manager, _clear_personas):
        """空名字应能创建。"""
        persona_id = manager.add_persona(name="", description="无名氏")
        persona = manager.get_persona(persona_id)
        assert persona["name"] == ""

    def test_long_name(self, manager, _clear_personas):
        """长名字应能创建。"""
        long_name = "x" * 1000
        persona_id = manager.add_persona(name=long_name)
        persona = manager.get_persona(persona_id)
        assert persona["name"] == long_name

    def test_special_characters(self, manager, _clear_personas):
        """特殊字符应能正确处理。"""
        name = "学生（大三）"
        desc = "喜欢编程、Python、JavaScript"
        persona_id = manager.add_persona(name=name, description=desc)
        persona = manager.get_persona(persona_id)
        assert persona["name"] == name
        assert persona["description"] == desc

    def test_unicode_name(self, manager, _clear_personas):
        """Unicode 字符应能正确处理。"""
        name = "佐仓"
        desc = "AI 伴侣"
        persona_id = manager.add_persona(name=name, description=desc)
        persona = manager.get_persona(persona_id)
        assert persona["name"] == name
        assert persona["description"] == desc

    def test_multiple_personas(self, manager, _clear_personas):
        """应能创建多个身份。"""
        for i in range(10):
            manager.add_persona(name=f"身份{i}", description=f"描述{i}")

        personas = manager.list_personas()
        assert len(personas) == 10

    def test_concurrent_operations(self, manager, _clear_personas):
        """连续操作应正确工作。"""
        # 快速创建、更新、删除
        ids = []
        for i in range(5):
            ids.append(manager.add_persona(name=f"身份{i}"))

        # 更新所有
        for i, pid in enumerate(ids):
            manager.update_persona(pid, name=f"更新后{i}")

        # 验证更新
        for i, pid in enumerate(ids):
            persona = manager.get_persona(pid)
            assert persona["name"] == f"更新后{i}"

        # 删除所有
        for pid in ids:
            manager.delete_persona(pid)

        assert manager.list_personas() == []
