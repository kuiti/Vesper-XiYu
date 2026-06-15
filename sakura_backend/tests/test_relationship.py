"""test_relationship.py — core.relationship 测试"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from core.relationship import (
    MIN_VALUE, MAX_VALUE, INITIAL_AFFECTION, INITIAL_TRUST,
    AI_EMOTIONS, EMOTION_BEHAVIOR_MAP,
    get_ai_emotion, get_emotion_behavior_hint,
    _progressive_multiplier, _cross_multiplier,
    switch_relationship_mode, adjust_relationship,
    get_relationship_hint, reset_relationship,
    LONG_TERM_SCALE, DAILY_CAP_AFFECTION, DAILY_CAP_TRUST,
)


# ═══════════════════════════════════════════════════════════════
# 常量检查
# ═══════════════════════════════════════════════════════════════


class TestConstants:
    def test_value_range(self):
        assert MIN_VALUE == -100
        assert MAX_VALUE == 100

    def test_initial_values(self):
        assert INITIAL_AFFECTION == 30
        assert INITIAL_TRUST == 30

    def test_ai_emotions_count(self):
        assert len(AI_EMOTIONS) == 12

    def test_emotion_behavior_map_covers_all_emotions(self):
        for emotion in AI_EMOTIONS:
            assert emotion in EMOTION_BEHAVIOR_MAP, f"Missing behavior for {emotion}"

    def test_long_term_scale(self):
        assert 0 < LONG_TERM_SCALE < 1

    def test_daily_caps_positive(self):
        assert DAILY_CAP_AFFECTION > 0
        assert DAILY_CAP_TRUST > 0


# ═══════════════════════════════════════════════════════════════
# get_ai_emotion — 情绪计算
# ═══════════════════════════════════════════════════════════════


class TestGetAiEmotion:
    @patch("core.relationship.get_relationship")
    def test_ecstatic(self, mock_rel):
        mock_rel.return_value = (85, 75)
        assert get_ai_emotion() == "ecstatic"

    @patch("core.relationship.get_relationship")
    def test_happy(self, mock_rel):
        mock_rel.return_value = (70, 60)
        assert get_ai_emotion() == "happy"

    @patch("core.relationship.get_relationship")
    def test_content(self, mock_rel):
        mock_rel.return_value = (55, 50)
        assert get_ai_emotion() == "content"

    @patch("core.relationship.get_relationship")
    def test_neutral(self, mock_rel):
        mock_rel.return_value = (35, 35)
        assert get_ai_emotion() == "neutral"

    @patch("core.relationship.get_relationship")
    def test_cautious(self, mock_rel):
        mock_rel.return_value = (25, 30)
        assert get_ai_emotion() == "cautious"

    @patch("core.relationship.get_relationship")
    def test_cold(self, mock_rel):
        mock_rel.return_value = (10, 30)
        assert get_ai_emotion() == "cold"

    @patch("core.relationship.get_relationship")
    def test_annoyed(self, mock_rel):
        mock_rel.return_value = (30, 25)
        assert get_ai_emotion() == "annoyed"

    @patch("core.relationship.get_relationship")
    def test_hurt(self, mock_rel):
        mock_rel.return_value = (40, 15)
        assert get_ai_emotion() == "hurt"

    @patch("core.relationship.get_relationship")
    def test_distrustful(self, mock_rel):
        mock_rel.return_value = (10, 10)
        assert get_ai_emotion() == "distrustful"

    @patch("core.relationship.get_relationship")
    def test_hostile(self, mock_rel):
        mock_rel.return_value = (-60, -60)
        assert get_ai_emotion() == "hostile"

    @patch("core.relationship.get_relationship")
    def test_betrayed(self, mock_rel):
        mock_rel.return_value = (10, -60)
        assert get_ai_emotion() == "betrayed"

    @patch("core.relationship.get_relationship")
    def test_resentful(self, mock_rel):
        mock_rel.return_value = (-60, 10)
        assert get_ai_emotion() == "resentful"


# ═══════════════════════════════════════════════════════════════
# _progressive_multiplier — 渐进乘数
# ═══════════════════════════════════════════════════════════════


class TestProgressiveMultiplier:
    # ─── 正增长 ───
    def test_positive_delta_low_current(self):
        """正值区间初期慢热。"""
        m = _progressive_multiplier(5, 1.0)
        assert m < 1.0  # 初期减速

    def test_positive_delta_mid_current(self):
        """正值区间中后期加速。"""
        m_low = _progressive_multiplier(20, 1.0)
        m_mid = _progressive_multiplier(60, 1.0)
        assert m_mid > m_low

    def test_positive_delta_high_current(self):
        """接近上限减速。"""
        m = _progressive_multiplier(95, 1.0)
        assert m < 1.2

    def test_positive_delta_negative_current(self):
        """负值区间正增长很难。"""
        m = _progressive_multiplier(-30, 1.0)
        assert m < 0.5

    def test_positive_delta_very_negative_current(self):
        """极负区间正增长极难。"""
        m = _progressive_multiplier(-80, 1.0)
        assert m < 0.2

    # ─── 负增长 ───
    def test_negative_delta_high_current(self):
        """正值区间负增长。"""
        m = _progressive_multiplier(90, -1.0)
        assert m <= 1.0

    def test_negative_delta_low_positive_current(self):
        """低正值区间负增长减速。"""
        m = _progressive_multiplier(10, -1.0)
        assert m < 1.0

    def test_negative_delta_negative_current(self):
        """负值区间触底保护。"""
        m = _progressive_multiplier(-80, -1.0)
        assert m < 0.2

    # ─── 零 delta ───
    def test_zero_delta(self):
        m = _progressive_multiplier(50, 0)
        assert m == 1.0


# ═══════════════════════════════════════════════════════════════
# _cross_multiplier — 双向牵制
# ═══════════════════════════════════════════════════════════════


class TestCrossMultiplier:
    @patch("core.relationship.get_relationship")
    def test_high_trust_boosts_affection(self, mock_rel):
        mock_rel.return_value = (50, 85)
        m = _cross_multiplier("affection")
        assert m >= 1.5

    @patch("core.relationship.get_relationship")
    def test_low_trust_reduces_affection(self, mock_rel):
        mock_rel.return_value = (50, 15)
        m = _cross_multiplier("affection")
        assert m < 1.0

    @patch("core.relationship.get_relationship")
    def test_high_affection_boosts_trust(self, mock_rel):
        mock_rel.return_value = (80, 50)
        m = _cross_multiplier("trust")
        assert m >= 1.5

    @patch("core.relationship.get_relationship")
    def test_negative_trust_extreme_penalty(self, mock_rel):
        mock_rel.return_value = (50, -60)
        m = _cross_multiplier("affection")
        assert m < 0.3

    @patch("core.relationship.get_relationship")
    def test_negative_affection_extreme_penalty(self, mock_rel):
        mock_rel.return_value = (-60, 50)
        m = _cross_multiplier("trust")
        assert m < 0.3

    @patch("core.relationship.get_relationship")
    def test_mid_values(self, mock_rel):
        mock_rel.return_value = (40, 40)
        m = _cross_multiplier("affection")
        assert m == 1.0


# ═══════════════════════════════════════════════════════════════
# switch_relationship_mode — 模式切换
# ═══════════════════════════════════════════════════════════════


class TestSwitchRelationshipMode:
    def test_invalid_mode(self):
        result = switch_relationship_mode("invalid")
        assert result["ok"] is False
        assert "无效" in result["error"]

    @patch("core.relationship.set_config")
    @patch("core.relationship.get_config")
    @patch("core.relationship.get_relationship")
    def test_same_mode_no_clamp(self, mock_rel, mock_get, mock_set):
        mock_rel.return_value = (50, 50)
        mock_get.side_effect = lambda key, default="": {
            "relationship_mode": "fast",
            "_rel_mode_locked_until": "",
        }.get(key, default)
        result = switch_relationship_mode("fast")
        assert result["ok"] is True
        assert result["clamped"] is False

    @patch("core.relationship._log_emotion_event")
    @patch("core.relationship.set_config")
    @patch("core.relationship.get_config")
    @patch("core.relationship.get_relationship")
    @patch("core.relationship.get_conn")
    def test_switch_to_long_term_clamps_high_values(self, mock_conn, mock_rel, mock_get, mock_set, mock_log):
        mock_rel.return_value = (90, 90)
        mock_get.side_effect = lambda key, default="": {
            "relationship_mode": "fast",
            "_rel_mode_locked_until": "",
        }.get(key, default)
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        result = switch_relationship_mode("long_term")
        assert result["ok"] is True
        assert result["clamped"] is True

    @patch("core.relationship.set_config")
    @patch("core.relationship.get_config")
    def test_cooldown_active(self, mock_get, mock_set):
        future = (datetime.now() + timedelta(hours=12)).isoformat()
        mock_get.side_effect = lambda key, default="": {
            "relationship_mode": "fast",
            "_rel_mode_locked_until": future,
        }.get(key, default)
        result = switch_relationship_mode("long_term")
        assert result["ok"] is False
        assert "冷却" in result["error"]


# ═══════════════════════════════════════════════════════════════
# adjust_relationship — 关系调整
# ═══════════════════════════════════════════════════════════════


class TestAdjustRelationship:
    @patch("core.relationship._log_emotion_event")
    @patch("core.relationship._update_value", return_value=0.1)
    def test_neutral_sentiment(self, mock_update, mock_log):
        adjust_relationship({"sentiment": "neutral", "target": "other", "intent": "statement", "relationship_impact": 0})
        assert mock_update.call_count == 2  # affection + trust

    @patch("core.relationship._log_emotion_event")
    @patch("core.relationship._update_value", return_value=0.1)
    def test_attack_ai_reduces_trust(self, mock_update, mock_log):
        adjust_relationship({"sentiment": "negative", "target": "ai", "intent": "attack", "relationship_impact": -1})
        # 应该有 trust_delta -= 1.0
        trust_calls = [c for c in mock_update.call_args_list if c[0][0] == "trust"]
        assert len(trust_calls) > 0
        assert trust_calls[0][0][1] < 0

    @patch("core.relationship._log_emotion_event")
    @patch("core.relationship._update_value", return_value=0.1)
    def test_sharing_increases_both(self, mock_update, mock_log):
        adjust_relationship({"sentiment": "positive", "target": "ai", "intent": "sharing", "relationship_impact": 0.5})
        # sharing 增加 trust +0.3 和 affection +0.15
        trust_calls = [c for c in mock_update.call_args_list if c[0][0] == "trust"]
        affection_calls = [c for c in mock_update.call_args_list if c[0][0] == "affection"]
        assert trust_calls[0][0][1] > 0
        assert affection_calls[0][0][1] > 0

    @patch("core.relationship._log_emotion_event")
    @patch("core.relationship._update_value", return_value=0.0)
    def test_none_sentiment(self, mock_update, mock_log):
        """None sentiment 不应崩溃。"""
        adjust_relationship(None)
        assert mock_update.call_count == 2

    @patch("core.relationship._log_emotion_event")
    @patch("core.relationship._update_value", return_value=0.0)
    def test_time_decay(self, mock_update, mock_log):
        """长时间未聊天应触发衰减。"""
        adjust_relationship(
            {"sentiment": "neutral", "target": "other", "intent": "statement", "relationship_impact": 0},
            hours_since_last=48
        )
        affection_calls = [c for c in mock_update.call_args_list if c[0][0] == "affection"]
        assert affection_calls[0][0][1] < 0  # 应该有 -0.5 衰减


# ═══════════════════════════════════════════════════════════════
# get_relationship_hint — 关系提示
# ═══════════════════════════════════════════════════════════════


class TestGetRelationshipHint:
    @patch("core.relationship.get_ai_emotion")
    @patch("core.relationship.get_relationship")
    def test_hint_contains_affection_trust(self, mock_rel, mock_emotion):
        mock_rel.return_value = (60, 60)
        mock_emotion.return_value = "happy"
        hint = get_relationship_hint()
        assert "好感:60" in hint or "好感" in hint
        assert "信任:60" in hint or "信任" in hint

    @patch("core.relationship.get_ai_emotion")
    @patch("core.relationship.get_relationship")
    def test_hint_contains_emotion(self, mock_rel, mock_emotion):
        mock_rel.return_value = (60, 60)
        mock_emotion.return_value = "happy"
        hint = get_relationship_hint()
        assert "开心" in hint


# ═══════════════════════════════════════════════════════════════
# get_emotion_behavior_hint — 情绪行为提示
# ═══════════════════════════════════════════════════════════════


class TestGetEmotionBehaviorHint:
    @patch("core.relationship.get_ai_emotion")
    def test_ecstatic_has_emoji(self, mock_emotion):
        mock_emotion.return_value = "ecstatic"
        hint = get_emotion_behavior_hint()
        assert "颜文字" in hint
        assert "热情" in hint

    @patch("core.relationship.get_ai_emotion")
    def test_cold_no_emoji(self, mock_emotion):
        mock_emotion.return_value = "cold"
        hint = get_emotion_behavior_hint()
        assert "少用颜文字" in hint

    @patch("core.relationship.get_ai_emotion")
    def test_hint_starts_with_marker(self, mock_emotion):
        mock_emotion.return_value = "neutral"
        hint = get_emotion_behavior_hint()
        assert hint.startswith("【语气参考")


# ═══════════════════════════════════════════════════════════════
# reset_relationship — 重置
# ═══════════════════════════════════════════════════════════════


class TestResetRelationship:
    @patch("core.relationship.set_config")
    @patch("core.relationship.invalidate_relationship_cache")
    @patch("core.relationship.get_conn")
    def test_reset_sets_initial_values(self, mock_conn, mock_invalidate, mock_set):
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        reset_relationship()
        # 应该写入 INITIAL_AFFECTION 和 INITIAL_TRUST
        calls = mock_cursor.execute.call_args_list
        affection_update = [c for c in calls if "affection" in str(c)]
        trust_update = [c for c in calls if "'trust'" in str(c)]
        assert len(affection_update) >= 1
        assert len(trust_update) >= 1