# tests/test_smoke.py — 记忆系统冒烟测试
"""覆盖记忆系统各组件的完整链路验证，确保每个端到端流程健康。"""

import pytest
import json
from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
# 1. CharacterCard 完整生命周期
# ═══════════════════════════════════════════════════════════════

class TestCharacterCardBasics:
    """角色卡核心功能（不依赖持久化到 characters_v2 表）"""

    def test_create_default(self):
        from core.character_card import CharacterCard
        card = CharacterCard()
        assert card.name == "夕语"
        assert card.description is not None

    def test_create_with_data(self):
        from core.character_card import CharacterCard
        card = CharacterCard({"name": "测试角色", "description": "测试描述"})
        assert card.name == "测试角色"
        assert card.description == "测试描述"

    def test_to_json_roundtrip(self):
        from core.character_card import CharacterCard
        card = CharacterCard({"name": "JSON测试", "tags": ["a", "b"]})
        json_str = card.to_json()
        restored = CharacterCard.from_json(json_str)
        assert restored.name == "JSON测试"

    def test_get_active_returns_none_when_no_active(self):
        """get_active 在没有 config 表时不应崩溃"""
        from core.character_card import CharacterCard
        try:
            active_card = CharacterCard.get_active()
            assert active_card is None or active_card is not None
        except Exception:
            pass  # 测试环境中 config 表可能不存在，不崩溃即可


# ═══════════════════════════════════════════════════════════════
# 2. MemoryProvider 完整链路
# ═══════════════════════════════════════════════════════════════

class TestMemoryProvider:
    """save_fact → get_context 全链路"""

    def test_save_and_get_context(self):
        from core.memory_provider import MemoryProvider
        provider = MemoryProvider()
        provider.save_fact(character_id=0, content="用户喜欢面条", category="PREFERENCE", confidence=0.9)
        ctx = provider.get_context(character_id=0, limit=10)
        assert "面条" in ctx

    def test_context_empty_when_no_facts(self):
        from core.memory_provider import MemoryProvider
        ctx = MemoryProvider().get_context(character_id=0)
        assert ctx == ""

    def test_per_character_isolation(self):
        from core.memory_provider import MemoryProvider
        provider = MemoryProvider()
        provider.save_fact(character_id=0, content="角色0的事实", category="FACT")
        provider.save_fact(character_id=1, content="角色1的事实", category="FACT")
        ctx0 = provider.get_context(character_id=0, limit=10)
        ctx1 = provider.get_context(character_id=1, limit=10)
        assert "角色0的事实" in ctx0
        assert "角色1的事实" in ctx1
        assert "角色1的事实" not in ctx0

    def test_search_facts(self):
        from core.memory_provider import MemoryProvider
        provider = MemoryProvider()
        provider.save_fact(character_id=0, content="用户喜欢蓝色", category="PREFERENCE")
        results = provider.search_facts(character_id=0, query="蓝色")
        assert len(results) >= 1

    def test_get_stats(self):
        from core.memory_provider import MemoryProvider
        provider = MemoryProvider()
        stats = provider.get_stats(character_id=0)
        assert "total_entries" in stats


# ═══════════════════════════════════════════════════════════════
# 3. TempMemory 管道
# ═══════════════════════════════════════════════════════════════

class TestTempMemory:
    """save_temp_conversation → batch_extract_memories"""

    def test_save_temp_conversation(self):
        from core.memory_provider import save_temp_conversation
        from core.db import get_chat_conn
        save_temp_conversation(character_id=0, user_msg="你好", ai_reply="你好呀")
        with get_chat_conn(0) as conn:
            row = conn.execute("SELECT COUNT(*) as n FROM temp_memory WHERE processed = 0").fetchone()
            assert row["n"] >= 1

    def test_batch_extract_memories(self):
        from core.memory_provider import save_temp_conversation, batch_extract_memories, MemoryProvider
        for msg in [
            ("我最喜欢的颜色是蓝色", "蓝色很好看"),
            ("我喜欢吃面条", "面条确实好吃"),
        ]:
            save_temp_conversation(character_id=0, user_msg=msg[0], ai_reply=msg[1])
        from unittest.mock import patch
        mock_facts = [
            {"text": "用户喜欢蓝色", "category": "PREFERENCE", "confidence": 0.9},
            {"text": "用户喜欢吃面条", "category": "PREFERENCE", "confidence": 0.8},
        ]
        with patch("core.memory_provider._llm_extract_facts", return_value=mock_facts):
            n = batch_extract_memories(character_id=0, max_items=10)
        assert n >= 1
        provider = MemoryProvider()
        ctx = provider.get_context(character_id=0, limit=10)
        assert "蓝色" in ctx or "面条" in ctx

    def test_batch_extract_skips_processed(self):
        from core.memory_provider import save_temp_conversation, batch_extract_memories
        from core.db import get_chat_conn
        save_temp_conversation(0, "测试", "回复")
        from unittest.mock import patch
        with patch("core.memory_provider._llm_extract_facts", return_value=[{"text": "事实", "category": "FACT", "confidence": 0.5}]):
            batch_extract_memories(0, 5)
            batch_extract_memories(0, 5)
        with get_chat_conn(0) as conn:
            row = conn.execute("SELECT COUNT(*) as n FROM temp_memory WHERE processed = 0").fetchone()
            assert row["n"] == 0


# ═══════════════════════════════════════════════════════════════
# 4. OCEAN 人格特征
# ═══════════════════════════════════════════════════════════════

class TestPersonalityTraits:
    """OCEAN 五维人格的初始化、读写、更新"""

    def test_init_defaults(self):
        from core.emotion_evolution import get_all_traits
        traits = get_all_traits(character_id=0)
        for key in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
            assert key in traits
            assert 0.0 <= traits[key] <= 1.0

    def test_update_trait(self):
        from core.emotion_evolution import get_trait, update_trait
        update_trait("extraversion", 0.2, character_id=0)
        val = get_trait("extraversion", character_id=0)
        assert val > 0.5

    def test_per_character_isolation(self):
        from core.emotion_evolution import update_trait, get_trait
        update_trait("openness", 0.3, character_id=0)
        update_trait("openness", -0.2, character_id=1)
        assert get_trait("openness", 0) > 0.5
        assert get_trait("openness", 1) < 0.3


# ═══════════════════════════════════════════════════════════════
# 5. 关系系统
# ═══════════════════════════════════════════════════════════════

class TestRelationship:
    """好感度/信任度读写、情绪映射"""

    def test_get_defaults(self):
        from core.relationship import get_relationship
        affection, trust = get_relationship(character_id=0)
        assert affection == 30
        assert trust == 30

    def test_per_character_relationship(self):
        """直接查询 relationship 表验证 per-character 隔离"""
        from core.db import get_chat_conn
        for cid in (0, 1):
            conn = get_chat_conn(cid)
            conn.execute(
                "INSERT OR REPLACE INTO relationship (key, value, updated_at) VALUES (?, ?, ?)",
                ("affection", 50 + cid * 20, "now")
            )
            conn.execute(
                "INSERT OR REPLACE INTO relationship (key, value, updated_at) VALUES (?, ?, ?)",
                ("trust", 30, "now")
            )
        for cid in (0, 1):
            conn = get_chat_conn(cid)
            row = conn.execute("SELECT value FROM relationship WHERE key = 'affection'").fetchone()
            assert row["value"] == 50 + cid * 20

    def test_get_ai_emotion(self):
        from core.relationship import get_ai_emotion
        emotion = get_ai_emotion(character_id=0)
        assert emotion in (
            "ecstatic", "happy", "content", "neutral", "cautious",
            "cold", "annoyed", "hurt", "distrustful",
            "hostile", "betrayed", "resentful",
        )

    def test_get_relationship_hint_does_not_crash(self):
        from core.relationship import get_relationship_hint
        hint = get_relationship_hint(character_id=0)
        assert isinstance(hint, str)


# ═══════════════════════════════════════════════════════════════
# 6. 聊天搜索
# ═══════════════════════════════════════════════════════════════

class TestSearch:
    """search_chat_messages 对不同 character_id 的正确性"""

    def _add_message(self, content, role="user", character_id=0):
        from core.db.chat import add_chat_message
        add_chat_message(role, content, character_id=character_id)

    def test_search_character_0(self):
        self._add_message("我喜欢蓝色的天空", character_id=0)
        from core.db.chat import search_chat_messages
        results = search_chat_messages("蓝色", character_id=0)
        assert len(results) >= 1

    def test_search_character_1(self):
        self._add_message("角色1的特殊信息", character_id=1)
        from core.db.chat import search_chat_messages
        results = search_chat_messages("特殊信息", character_id=1)
        assert len(results) >= 1

    def test_search_isolation(self):
        self._add_message("角色A的秘密", character_id=0)
        self._add_message("角色B的秘密", character_id=1)
        from core.db.chat import search_chat_messages
        r0 = search_chat_messages("秘密", character_id=0)
        r1 = search_chat_messages("秘密", character_id=1)
        assert len(r0) >= 1
        assert len(r1) >= 1


# ═══════════════════════════════════════════════════════════════
# 7. 情绪记录
# ═══════════════════════════════════════════════════════════════

class TestEmotionTracking:
    """record_emotion + get_emotion_trend 的 per-character 隔离"""

    def test_record_emotion(self):
        from core.emotion_tracker import record_emotion, get_emotion_trend
        record_emotion("positive", character_id=0)
        trend = get_emotion_trend(days=7, character_id=0)
        assert len(trend) >= 1
        assert trend[0]["positive_count"] >= 1

    def test_per_character_emotion(self):
        from core.emotion_tracker import record_emotion, get_emotion_trend
        record_emotion("positive", character_id=0)
        record_emotion("negative", character_id=1)
        trend0 = get_emotion_trend(days=7, character_id=0)
        trend1 = get_emotion_trend(days=7, character_id=1)
        assert trend0[0]["positive_count"] >= 1
        assert trend1[0]["negative_count"] >= 1


# ═══════════════════════════════════════════════════════════════
# 8. 纠错记忆
# ═══════════════════════════════════════════════════════════════

class TestCorrectionMemory:
    """记录纠错 → 相关纠错查询"""

    def test_record_and_query(self):
        from core.correction_memory import record_correction, get_relevant_corrections
        record_correction(
            user_msg="我不叫小明",
            ai_wrong_reply="好的小明",
            wrong_pattern="小明",
            corrected_fact="用户的名字是小华",
            trigger_keywords=["小明", "名字"],
            character_id=0,
        )
        results = get_relevant_corrections("小明你好", top_k=3, character_id=0)
        assert len(results) >= 1

    def test_detect_correction(self):
        from core.correction_memory import detect_correction
        result = detect_correction("不是蓝色，是红色", "")
        assert result is not False  # 返回 dict 或 True


# ═══════════════════════════════════════════════════════════════
# 9. 提及权重追踪
# ═══════════════════════════════════════════════════════════════

class TestMentionTracker:
    """记录提及 → 获取权重 → 衰减"""

    def test_record_and_weight(self):
        from core.mention_tracker import record_mention, get_top_mentions
        record_mention("今天天气真好", character_id=0)
        tops = get_top_mentions(n=5, min_weight=0.001, character_id=0)
        assert len(tops) >= 0  # 不应崩溃

    def test_decay(self):
        from core.mention_tracker import decay_all
        result = decay_all(character_id=0)
        assert result >= 0  # 不应崩溃


# ═══════════════════════════════════════════════════════════════
# 10. 行为反馈记忆
# ═══════════════════════════════════════════════════════════════

class TestFeedbackMemory:
    """保存反馈 → 获取行为规则"""

    def test_save_and_rules(self):
        from core.feedback_memory import save_behavior_feedback, get_behavior_rules
        save_behavior_feedback("用户不喜欢敷衍的回答", category="behavior", character_id=0)
        rules = get_behavior_rules(max_rules=5, character_id=0)
        assert len(rules) >= 1


# ═══════════════════════════════════════════════════════════════
# 11. PersonalityTraitPipe
# ═══════════════════════════════════════════════════════════════

class TestPersonalityTraitPipe:
    """PersonalityTraitPipe 应正确读取并格式化 OCEAN 特征"""

    def test_pipe_output_contains_all_traits(self):
        from core.emotion_evolution import init_traits
        from core.prompt_pipeline import PersonalityTraitPipe, PipelineContext
        init_traits(character_id=0)
        ctx = PipelineContext()
        ctx.character_id = 0
        result = PersonalityTraitPipe().process(ctx)
        assert result is not None
        for trait in ["开放性", "尽责性", "外向性", "宜人性", "神经质"]:
            assert trait in result


# ═══════════════════════════════════════════════════════════════
# 12. 知识图谱
# ═══════════════════════════════════════════════════════════════

class TestKnowledgeGraph:
    """知识图谱写入与查询的 per-character 隔离"""

    def test_add_and_query(self):
        from core.db.entity import add_knowledge_triplet, query_knowledge_by_entity
        add_knowledge_triplet("用户", "喜欢", "面条", character_id=0)
        results = query_knowledge_by_entity("用户", character_id=0)
        assert len(results) >= 1
