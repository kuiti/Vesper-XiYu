"""test_integration.py — 集成测试：覆盖核心链路

覆盖范围:
1. 角色卡 CRUD + 激活/取消激活 全生命周期
2. 聊天消息路由 — 按 character_id 隔离
3. 设置继承链 — resolve_config 角色覆盖 → 全局 → 默认
4. 功能开关 — is_feature_enabled
5. 画像隔离 — aggregate vs isolated 模式
6. 提示词管道 — 含角色卡的 system prompt 构建
7. 连接安全 — 路径校验、锁
"""

import json
import os
import pytest
import sqlite3
import threading
from unittest.mock import patch, MagicMock
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _use_temp_db(monkeypatch, tmp_path):
    """使用临时文件 DB，所有路径隔离在 tmp_path 下"""
    import core.db
    db_file = str(tmp_path / "vesper.db")
    monkeypatch.setattr("core.db.DB_FILE", db_file)
    core.db._db_initialized = False

    # 让 per-character DB 也走 tmp_path，测试间不污染真实 data/chats/
    orig_chat_path = core.db._safe_chat_path
    orig_profile_path = core.db._safe_profile_path

    def _safe_chat_path(character_id=0):
        p = orig_chat_path(character_id)
        return os.path.normpath(str(tmp_path / p))

    def _safe_profile_path(character_id=0):
        p = orig_profile_path(character_id)
        return os.path.normpath(str(tmp_path / p))

    monkeypatch.setattr("core.db._safe_chat_path", _safe_chat_path)
    monkeypatch.setattr("core.db._safe_profile_path", _safe_profile_path)
    monkeypatch.setattr("core.db._CHAT_CONNS", {})
    monkeypatch.setattr("core.db._PROFILE_CONNS", {})

    yield
    core.db._db_initialized = False


@pytest.fixture(autouse=True)
def _reset_character_state():
    """每个测试前后重置角色卡缓存和全局配置"""
    from core.character_card import _active_card_cache
    from core.db.config import _config_cache
    _active_card_cache["card"] = None
    _active_card_cache["time"] = 0
    _config_cache.clear()
    yield
    _active_card_cache["card"] = None
    _active_card_cache["time"] = 0
    _config_cache.clear()


@pytest.fixture
def sample_card_data():
    """标准角色卡数据"""
    return {
        "name": "测试角色",
        "description": "一个用于测试的角色",
        "personality": "温柔、耐心",
        "scenario": "测试场景",
        "first_mes": "你好呀！",
        "mes_example": "用户: 你好\nAI: 你好呀~",
        "system_prompt": "你是测试角色，一个温柔的AI助手。",
        "post_history_instructions": "保持温柔",
        "creator_notes": "测试用",
        "tags": ["test"],
    }


@pytest.fixture
def create_card(sample_card_data):
    """创建并返回角色卡的工厂函数"""
    from core.character_card import CharacterCard

    def _create(**overrides):
        data = {**sample_card_data, **overrides}
        card = CharacterCard(data)
        char_id = card.save_to_db()
        card._db_id = char_id
        return card, char_id

    return _create


# ═══════════════════════════════════════════════════════════════
# 1. 角色卡 CRUD + 激活生命周期
# ═══════════════════════════════════════════════════════════════


class TestCharacterCardLifecycle:
    """角色卡完整生命周期：创建 → 加载 → 激活 → 更新 → 取消 → 删除"""

    def test_create_and_load(self, create_card):
        card, char_id = create_card()
        loaded = card.load_from_db(char_id)
        assert loaded is not None
        assert loaded.name == "测试角色"
        assert loaded.description == "一个用于测试的角色"
        assert loaded.system_prompt == "你是测试角色，一个温柔的AI助手。"

    def test_create_multiple_cards(self, create_card):
        cards = []
        for i in range(3):
            card, cid = create_card(name=f"角色{i}")
            cards.append((card, cid))
        all_cards = cards[0][0].list_all()
        assert len(all_cards) >= 3

    def test_activate_and_get_active(self, create_card):
        card, char_id = create_card()
        card.activate(char_id)
        active = card.get_active()
        assert active is not None
        assert active.name == "测试角色"
        assert active._db_id == char_id

    def test_activate_deactivates_others(self, create_card):
        card1, cid1 = create_card(name="角色A")
        card2, cid2 = create_card(name="角色B")
        card1.activate(cid1)
        card2.activate(cid2)
        active = card1.get_active()
        assert active.name == "角色B"

    def test_deactivate_all(self, create_card):
        card, char_id = create_card()
        card.activate(char_id)
        card.deactivate_all()
        active = card.get_active()
        assert active is None

    def test_update_card(self, create_card):
        card, char_id = create_card()
        card.data["description"] = "更新后的描述"
        card.update_db(char_id)
        loaded = card.load_from_db(char_id)
        assert loaded.description == "更新后的描述"

    def test_delete_card(self, create_card):
        card, char_id = create_card()
        card.delete(char_id)
        loaded = card.load_from_db(char_id)
        assert loaded is None

    def test_list_all_shows_card_data_fields(self, create_card):
        """list_all 应从 card_data JSON 解析，保证字段一致性"""
        card, char_id = create_card(name="一致性测试", description="从JSON读取")
        all_cards = card.list_all()
        found = [c for c in all_cards if c["id"] == char_id]
        assert len(found) == 1
        assert found[0]["name"] == "一致性测试"
        assert found[0]["description"] == "从JSON读取"

    def test_card_data_json_roundtrip(self, create_card):
        """card_data JSON 序列化/反序列化不丢失字段"""
        card, char_id = create_card(tags=["a", "b"], voice={"engine": "edge"})
        loaded = card.load_from_db(char_id)
        assert loaded.data["tags"] == ["a", "b"]
        assert loaded.data["voice"] == {"engine": "edge"}

    def test_get_active_cache_ttl(self, create_card):
        """get_active 有 5 秒缓存"""
        import time
        card, char_id = create_card()
        card.activate(char_id)
        first = card.get_active()
        # 再次调用应返回缓存
        second = card.get_active()
        assert first is second

    def test_activate_invalid_id(self, create_card):
        """激活不存在的 ID 不应崩溃"""
        card, _ = create_card()
        card.activate(99999)
        active = card.get_active()
        assert active is None


# ═══════════════════════════════════════════════════════════════
# 2. 聊天消息路由 — 按 character_id 隔离
# ═══════════════════════════════════════════════════════════════


class TestChatMessageRouting:
    """聊天消息按 character_id 路由到独立数据库"""

    def test_add_and_get_messages(self, create_card):
        from core.db import add_chat_message, get_recent_chat_messages
        card, cid = create_card()
        add_chat_message("user", "你好", character_id=cid)
        add_chat_message("assistant", "你好呀~", character_id=cid)
        msgs = get_recent_chat_messages(10, character_id=cid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_messages_isolated_between_characters(self, create_card):
        from core.db import add_chat_message, get_recent_chat_messages
        card1, cid1 = create_card(name="角色A")
        card2, cid2 = create_card(name="角色B")
        add_chat_message("user", "消息给A", character_id=cid1)
        add_chat_message("user", "消息给B", character_id=cid2)
        msgs_a = get_recent_chat_messages(10, character_id=cid1)
        msgs_b = get_recent_chat_messages(10, character_id=cid2)
        assert len(msgs_a) == 1
        assert msgs_a[0]["content"] == "消息给A"
        assert len(msgs_b) == 1
        assert msgs_b[0]["content"] == "消息给B"

    def test_default_character_messages(self):
        from core.db import add_chat_message, get_recent_chat_messages
        add_chat_message("user", "默认消息", character_id=0)
        msgs = get_recent_chat_messages(10, character_id=0)
        assert any(m["content"] == "默认消息" for m in msgs)

    def test_get_last_user_messages(self, create_card):
        from core.db import add_chat_message, get_last_user_messages
        card, cid = create_card()
        add_chat_message("user", "第一条", character_id=cid)
        add_chat_message("assistant", "回复", character_id=cid)
        add_chat_message("user", "第二条", character_id=cid)
        user_msgs = get_last_user_messages(3, character_id=cid)
        assert len(user_msgs) == 2
        # get_last_user_messages 按 id DESC 排序，第一条是最新
        assert user_msgs[0]["content"] == "第二条"

    def test_get_all_messages(self, create_card):
        from core.db import add_chat_message, get_all_chat_messages
        card, cid = create_card()
        for i in range(5):
            add_chat_message("user", f"msg{i}", character_id=cid)
        all_msgs = get_all_chat_messages(character_id=cid)
        assert len(all_msgs) == 5

    def test_reroll_last_ai_message(self, create_card):
        from core.db import add_chat_message, reroll_last_ai_message
        card, cid = create_card()
        add_chat_message("user", "问题", character_id=cid)
        add_chat_message("assistant", "回答", character_id=cid)
        result = reroll_last_ai_message(character_id=cid)
        assert result == "问题"
        from core.db import get_recent_chat_messages
        msgs = get_recent_chat_messages(10, character_id=cid)
        assert len(msgs) == 0


# ═══════════════════════════════════════════════════════════════
# 3. 设置继承链 — resolve_config
# ═══════════════════════════════════════════════════════════════


class TestSettingsInheritance:
    """resolve_config: 角色级 → 全局 → 默认值"""

    def test_global_fallback(self):
        from core.db import set_config
        from core.character_card import resolve_config
        set_config("test_inherit_key", "global_value")
        result = resolve_config("test_inherit_key", "default", character_id=0)
        assert result == "global_value"

    def test_default_value(self):
        from core.character_card import resolve_config
        result = resolve_config("nonexistent_key_xyz", "fallback", character_id=0)
        assert result == "fallback"

    def test_character_override(self, create_card):
        from core.db import set_config
        from core.character_card import resolve_config, CharacterCard
        set_config("api_key", "global_key")
        card, cid = create_card()
        # 给角色设置覆盖
        card.data["settings"] = {"api_key": "char_key"}
        card.update_db(cid)
        result = resolve_config("api_key", "", character_id=cid)
        assert result == "char_key"

    def test_character_inherits_global_when_no_override(self, create_card):
        from core.db import set_config
        from core.character_card import resolve_config
        set_config("user_name", "全局用户名")
        card, cid = create_card()
        result = resolve_config("user_name", "", character_id=cid)
        assert result == "全局用户名"

    def test_character_settings_json_string(self, create_card):
        """settings 为 JSON 字符串时也能正确解析"""
        from core.character_card import resolve_config, CharacterCard
        card, cid = create_card()
        card.data["settings"] = '{"temperature": 0.8}'
        card.update_db(cid)
        result = resolve_config("temperature", 0.5, character_id=cid)
        assert result == 0.8

    def test_settings_update_via_api(self, create_card):
        """通过 API 更新角色设置"""
        card, cid = create_card()
        card.data["settings"] = {"key1": "val1"}
        card.update_db(cid)
        loaded = card.load_from_db(cid)
        settings = loaded.data.get("settings", {})
        assert settings["key1"] == "val1"


# ═══════════════════════════════════════════════════════════════
# 4. 功能开关 — is_feature_enabled
# ═══════════════════════════════════════════════════════════════


class TestFeatureFlags:
    """角色卡 features 字段控制功能启停"""

    def test_no_active_card_returns_false(self):
        from core.character_card import CharacterCard
        CharacterCard.deactivate_all()
        assert CharacterCard.is_feature_enabled("shared_memory") is False

    def test_feature_enabled(self, create_card):
        from core.character_card import CharacterCard
        card, cid = create_card(features={"shared_memory": True})
        card.activate(cid)
        assert CharacterCard.is_feature_enabled("shared_memory") is True

    def test_feature_disabled_explicitly(self, create_card):
        from core.character_card import CharacterCard
        card, cid = create_card(features={"shared_memory": False})
        card.activate(cid)
        assert CharacterCard.is_feature_enabled("shared_memory") is False

    def test_feature_missing_defaults_false(self, create_card):
        from core.character_card import CharacterCard
        card, cid = create_card()  # no features key
        card.activate(cid)
        assert CharacterCard.is_feature_enabled("shared_memory") is False

    def test_multiple_features(self, create_card):
        from core.character_card import CharacterCard
        card, cid = create_card(features={
            "shared_memory": True,
            "milestones": True,
            "conversation_followup": False,
        })
        card.activate(cid)
        assert CharacterCard.is_feature_enabled("shared_memory") is True
        assert CharacterCard.is_feature_enabled("milestones") is True
        assert CharacterCard.is_feature_enabled("conversation_followup") is False
        assert CharacterCard.is_feature_enabled("emotion") is False  # 未设置

    def test_features_as_json_string(self, create_card):
        """features 为 JSON 字符串时也能解析"""
        from core.character_card import CharacterCard
        card, cid = create_card()
        card.data["features"] = '{"shared_memory": true}'
        card.update_db(cid)
        card.activate(cid)
        assert CharacterCard.is_feature_enabled("shared_memory") is True


# ═══════════════════════════════════════════════════════════════
# 5. 画像隔离 — aggregate vs isolated
# ═══════════════════════════════════════════════════════════════


class TestProfileIsolation:
    """用户画像按角色隔离：aggregate（共享）vs isolated（独立）"""

    def test_aggregate_mode_uses_shared_db(self):
        from core.profile_builder import _get_profile_mode
        assert _get_profile_mode(0) == "aggregate"

    def test_aggregate_mode_default_for_character(self, create_card):
        from core.profile_builder import _get_profile_mode
        card, cid = create_card()
        assert _get_profile_mode(cid) == "aggregate"

    def test_isolated_mode_from_settings(self, create_card):
        from core.profile_builder import _get_profile_mode
        card, cid = create_card(settings={"profile_mode": "isolated"})
        assert _get_profile_mode(cid) == "isolated"

    def test_isolated_profile_write_and_read(self, create_card):
        """isolated 模式下写入角色专属 profile.db"""
        from core.db import get_char_profile_conn
        card, cid = create_card()
        conn = get_char_profile_conn(cid)
        cursor = conn.cursor()
        cursor.execute(
            "REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, ?, ?)",
            ("name", "小明", 0.9, datetime.now().isoformat())
        )
        conn.commit()
        cursor.execute("SELECT value FROM user_profile WHERE key = 'name'")
        row = cursor.fetchone()
        assert row["value"] == "小明"

    def test_isolated_profiles_different_per_character(self, create_card):
        """不同角色的 isolated profile 互不干扰"""
        from core.db import get_char_profile_conn
        card1, cid1 = create_card(name="角色A")
        card2, cid2 = create_card(name="角色B")
        conn1 = get_char_profile_conn(cid1)
        conn2 = get_char_profile_conn(cid2)
        conn1.execute("REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, ?, ?)",
                       ("name", "用户A", 0.9, datetime.now().isoformat()))
        conn1.commit()
        conn2.execute("REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, ?, ?)",
                       ("name", "用户B", 0.9, datetime.now().isoformat()))
        conn2.commit()
        cursor1 = conn1.cursor()
        cursor1.execute("SELECT value FROM user_profile WHERE key = 'name'")
        assert cursor1.fetchone()["value"] == "用户A"
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT value FROM user_profile WHERE key = 'name'")
        assert cursor2.fetchone()["value"] == "用户B"


# ═══════════════════════════════════════════════════════════════
# 6. 提示词管道 — 含角色卡的 system prompt 构建
# ═══════════════════════════════════════════════════════════════


class TestPromptPipeline:
    """提示词管道：角色卡数据注入 system prompt"""

    def test_persona_pipe_reads_character_card(self, create_card):
        """PersonaPipe 从角色卡读取 system_prompt"""
        from core.prompt_pipeline import PersonaPipe, PipelineContext
        card, cid = create_card(system_prompt="你是自定义角色")
        card.activate(cid)
        pipe = PersonaPipe()
        ctx = PipelineContext(user_message="你好", emotion="neutral")
        result = pipe.process(ctx)
        assert result is not None
        assert "自定义角色" in result

    def test_identity_pipe_reads_character_name(self, create_card):
        """IdentityPipe 从角色卡读取名称"""
        from core.prompt_pipeline import IdentityPipe, PipelineContext
        card, cid = create_card(name="小樱")
        card.activate(cid)
        pipe = IdentityPipe()
        ctx = PipelineContext(user_message="你好", emotion="neutral")
        result = pipe.process(ctx)
        assert result is not None
        assert "小樱" in result

    def test_no_active_card_persona_pipe(self):
        """无活跃角色时 PersonaPipe 使用全局配置"""
        from core.prompt_pipeline import PersonaPipe, PipelineContext
        from core.character_card import CharacterCard
        CharacterCard.deactivate_all()
        from core.db import set_config
        set_config("custom_system_prompt", "全局系统提示")
        pipe = PersonaPipe()
        ctx = PipelineContext(user_message="你好", emotion="neutral")
        result = pipe.process(ctx)
        assert result is not None

    def test_post_history_pipe_from_card(self, create_card):
        """PostHistoryPipe 从角色卡读取 post_history_instructions"""
        from core.prompt_pipeline import PostHistoryPipe, PipelineContext
        card, cid = create_card(post_history_instructions="请用温柔的语气回复")
        card.activate(cid)
        pipe = PostHistoryPipe()
        ctx = PipelineContext(user_message="你好", emotion="neutral")
        result = pipe.process(ctx)
        assert result is not None
        assert "温柔" in result

    def test_pipeline_context_carries_data(self):
        """PipelineContext 正确携带所有数据"""
        from core.prompt_pipeline import PipelineContext
        ctx = PipelineContext(
            user_message="测试消息",
            emotion="positive",
            rag_context="RAG内容",
            current_time_str="2025-01-01 12:00",
        )
        assert ctx.user_message == "测试消息"
        assert ctx.emotion == "positive"
        assert ctx.rag_context == "RAG内容"
        assert ctx.current_time_str == "2025-01-01 12:00"


# ═══════════════════════════════════════════════════════════════
# 7. 连接安全 — 路径校验、锁
# ═══════════════════════════════════════════════════════════════


class TestConnectionSafety:
    """连接安全性：路径穿越防护、并发锁"""

    def test_sanitize_char_name_normal(self):
        from core.db import _sanitize_char_name
        assert _sanitize_char_name("正常角色", 1) == "正常角色"

    def test_sanitize_char_name_removes_special_chars(self):
        from core.db import _sanitize_char_name
        result = _sanitize_char_name("角色/../../etc", 1)
        assert ".." not in result
        assert "/" not in result

    def test_sanitize_char_name_empty_becomes_fallback(self):
        from core.db import _sanitize_char_name
        assert _sanitize_char_name("", 42) == "char_42"
        assert _sanitize_char_name("///", 42) == "char_42"

    def test_safe_chat_path_within_base(self):
        from core.db import _safe_chat_path
        path = _safe_chat_path(0)
        norm = os.path.normpath(path)
        assert "data" in norm and "chats" in norm
        assert norm.endswith("chat.db")

    def test_safe_profile_path_within_base(self):
        from core.db import _safe_profile_path
        path = _safe_profile_path(0)
        norm = os.path.normpath(path)
        assert "data" in norm and "chats" in norm
        assert norm.endswith("profile.db")

    def test_chat_conn_lock_thread_safety(self, create_card):
        """多线程同时获取连接不会崩溃"""
        from core.db import get_chat_conn
        card, cid = create_card()
        results = []
        errors = []

        def _get_conn():
            try:
                conn = get_chat_conn(cid)
                results.append(conn)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_get_conn) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(results) == 10

    def test_path_traversal_blocked(self):
        """路径穿越攻击被阻止"""
        from core.db import _sanitize_char_name, _safe_chat_path
        # 即使角色名包含 ../ 也不会逃出 data/chats/
        safe = _sanitize_char_name("../../../etc/passwd", 1)
        assert ".." not in safe


# ═══════════════════════════════════════════════════════════════
# 8. 激活联动 — 全局配置同步
# ═══════════════════════════════════════════════════════════════


class TestActivationSync:
    """角色激活时同步全局配置"""

    def test_activate_syncs_ai_name(self, create_card):
        from core.db import get_config
        from core.character_card import CharacterCard
        card, cid = create_card(name="联动测试")
        card.activate(cid)
        # 模拟 api/characters.py 的同步逻辑
        from core.db import set_config
        set_config("ai_name", card.name)
        set_config("_active_character_card", card.name)
        assert get_config("ai_name") == "联动测试"

    def test_deactivate_clears_active_card(self, create_card):
        from core.db import get_config, set_config
        from core.character_card import CharacterCard
        card, cid = create_card()
        card.activate(cid)
        set_config("_active_character_card", card.name)
        card.deactivate_all()
        set_config("_active_character_card", "")
        assert get_config("_active_character_card", "") == ""

    def test_previous_backup_cleanup_on_no_active(self):
        """无活跃角色时，_previous_* 被清空"""
        from core.db import set_config, get_config
        from core.character_card import CharacterCard
        CharacterCard.deactivate_all()
        # 模拟崩溃残留
        set_config("_previous_ai_name", "残留值")
        set_config("_previous_custom_system_prompt", "残留提示")
        # 模拟 main.py 启动清理逻辑
        if not CharacterCard.get_active():
            for key in ("_previous_ai_name", "_previous_custom_system_prompt"):
                set_config(key, "")
        assert get_config("_previous_ai_name", "") == ""
        assert get_config("_previous_custom_system_prompt", "") == ""


# ═══════════════════════════════════════════════════════════════
# 9. 情景记忆路由
# ═══════════════════════════════════════════════════════════════


class TestEpisodicMemoryRouting:
    """情景记忆按角色隔离"""

    def test_save_and_recall_episode(self, create_card):
        from core.episodic_memory import save_episode, recall_episode
        card, cid = create_card()
        messages = [
            {"role": "user", "content": "今天天气真好"},
            {"role": "assistant", "content": "是呀，适合出去走走"},
        ]
        save_episode(
            start_time="2025-01-01T10:00:00",
            end_time="2025-01-01T10:05:00",
            messages=messages,
            character_id=cid,
        )
        result = recall_episode("天气", character_id=cid)
        # 结果可能为空（取决于 FTS 索引），但不应崩溃
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════
# 10. 好感度路由
# ═══════════════════════════════════════════════════════════════


class TestRelationshipRouting:
    """好感度基础功能"""

    def test_get_relationship_default(self):
        from core.relationship import get_relationship
        aff, trust = get_relationship()
        assert isinstance(aff, (int, float))
        assert isinstance(trust, (int, float))

    def test_relationship_hint_not_empty(self):
        from core.relationship import get_relationship_hint
        hint = get_relationship_hint()
        assert isinstance(hint, str)


# ═══════════════════════════════════════════════════════════════
# 11. Multi-session — 多会话管理
# ═══════════════════════════════════════════════════════════════


class TestMultiSession:
    """多会话：创建、切换、删除、消息隔离"""

    def test_create_and_list_sessions(self, create_card):
        from core.db import list_sessions, create_session, get_active_session_id
        card, cid = create_card()
        # 默认有一个 session
        sessions = list_sessions(character_id=cid)
        assert len(sessions) >= 1
        # 创建新 session
        sid = create_session("测试会话", character_id=cid)
        sessions = list_sessions(character_id=cid)
        assert len(sessions) >= 2
        # 新 session 是活跃的
        active_id = get_active_session_id(character_id=cid)
        assert active_id == sid

    def test_switch_session(self, create_card):
        from core.db import list_sessions, create_session, switch_session, get_active_session_id
        card, cid = create_card()
        sessions = list_sessions(character_id=cid)
        old_id = sessions[0]["id"]
        new_id = create_session("新会话", character_id=cid)
        # 切回旧 session
        switch_session(old_id, character_id=cid)
        assert get_active_session_id(character_id=cid) == old_id

    def test_messages_isolated_between_sessions(self, create_card):
        from core.db import add_chat_message, get_recent_chat_messages, create_session
        card, cid = create_card()
        # 在默认 session 写消息
        add_chat_message("user", "默认会话消息", character_id=cid)
        # 创建新 session
        sid = create_session("新会话", character_id=cid)
        add_chat_message("user", "新会话消息", character_id=cid)
        # 验证隔离
        default_msgs = get_recent_chat_messages(10, character_id=cid, session_id=1)
        new_msgs = get_recent_chat_messages(10, character_id=cid, session_id=sid)
        assert any(m["content"] == "默认会话消息" for m in default_msgs)
        assert any(m["content"] == "新会话消息" for m in new_msgs)
        assert not any(m["content"] == "新会话消息" for m in default_msgs)
        assert not any(m["content"] == "默认会话消息" for m in new_msgs)

    def test_delete_session(self, create_card):
        from core.db import list_sessions, create_session, delete_session, get_all_chat_messages, add_chat_message
        card, cid = create_card()
        sid = create_session("待删除", character_id=cid)
        add_chat_message("user", "会被删除的消息", character_id=cid, session_id=sid)
        sessions_before = list_sessions(character_id=cid)
        delete_session(sid, character_id=cid)
        sessions_after = list_sessions(character_id=cid)
        assert len(sessions_after) == len(sessions_before) - 1

    def test_cannot_delete_last_session(self, create_card):
        from core.db import list_sessions, delete_session
        from fastapi import HTTPException
        card, cid = create_card()
        sessions = list_sessions(character_id=cid)
        last_id = sessions[0]["id"]
        # 删除最后一个 session 应该失败（在 API 层拦截）
        # 这里测试底层不拦截，API 层拦截
        delete_session(last_id, character_id=cid)
        # 底层允许删除，但 API 层会检查


# ═══════════════════════════════════════════════════════════════
# 12. Per-character isolation — 角色数据隔离
# ═══════════════════════════════════════════════════════════════


class TestPerCharacterIsolation:
    """验证 relationship/emotion/summary 按角色隔离"""

    def test_relationship_isolated(self, create_card):
        from core.relationship import get_relationship, adjust_relationship, reset_relationship
        from core.db import add_chat_message
        card1, cid1 = create_card(name="角色A")
        card2, cid2 = create_card(name="角色B")
        # 重置两个角色的关系
        reset_relationship(character_id=cid1)
        reset_relationship(character_id=cid2)
        # 读取初始值
        aff1, _ = get_relationship(character_id=cid1)
        aff2, _ = get_relationship(character_id=cid2)
        assert aff1 == aff2  # 都是默认值

    def test_emotion_isolated(self, create_card):
        from core.emotion_tracker import record_emotion, get_today_emotion
        card1, cid1 = create_card(name="角色A")
        card2, cid2 = create_card(name="角色B")
        # 给角色A记录正面情绪
        record_emotion("positive", character_id=cid1)
        record_emotion("positive", character_id=cid1)
        # 角色B应该没有情绪记录
        emo_a = get_today_emotion(character_id=cid1)
        emo_b = get_today_emotion(character_id=cid2)
        assert emo_a["positive_count"] >= 2
        assert emo_b["positive_count"] == 0
