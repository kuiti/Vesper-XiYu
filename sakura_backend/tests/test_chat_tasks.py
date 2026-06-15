"""test_chat_tasks.py — api.chat_tasks 纯函数 + 逻辑测试"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from api.chat_tasks import (
    _clean_dsml,
    _build_depth_hint,
    _parse_dsml_tool_calls,
    _apply_background_update,
    REMINDER_RULES,
)


# ═══════════════════════════════════════════════════════════════
# _clean_dsml — DSML 清理
# ═══════════════════════════════════════════════════════════════


class TestCleanDSML:
    def test_no_dsml(self):
        assert _clean_dsml("hello world") == "hello world"

    def test_empty_string(self):
        assert _clean_dsml("") == ""

    def test_preserves_normal_text(self):
        text = "这是一段正常的中文消息"
        assert _clean_dsml(text) == text

    def test_removes_dsml_tool_calls_block(self):
        text = 'before<||DSML||tool_calls>invoke stuff</||DSML||tool_calls>after'
        result = _clean_dsml(text)
        assert "DSML" not in result
        assert "invoke" not in result
        assert "before" in result
        assert "after" in result

    def test_removes_dsml_open_tags(self):
        text = '<||DSML||invoke name="weather">'
        result = _clean_dsml(text)
        assert "DSML" not in result

    def test_removes_dsml_close_tags(self):
        text = '</||DSML||invoke>'
        result = _clean_dsml(text)
        assert "DSML" not in result

    def test_multiple_dsml_blocks(self):
        text = '<||DSML||tool_calls>a</||DSML||tool_calls>中<||DSML||tool_calls>b</||DSML||tool_calls>'
        result = _clean_dsml(text)
        assert "DSML" not in result
        assert "中" in result

    def test_strips_whitespace(self):
        text = "  hello  "
        assert _clean_dsml(text) == "hello"


# ═══════════════════════════════════════════════════════════════
# _build_depth_hint — 深度提示
# ═══════════════════════════════════════════════════════════════


class TestBuildDepthHint:
    def test_empty_message(self):
        result = _build_depth_hint("", "neutral")
        # 空消息长度 < 5，应有短回复提示
        assert "短" in result or result == ""

    def test_negative_emotion(self):
        result = _build_depth_hint("我今天好难过啊", "negative")
        assert "温柔" in result

    def test_positive_emotion(self):
        result = _build_depth_hint("今天天气真好", "positive")
        assert "活跃" in result

    def test_short_message(self):
        result = _build_depth_hint("嗯", "neutral")
        assert "短" in result

    def test_long_message(self):
        msg = "这是一段很长很长的消息" * 10
        result = _build_depth_hint(msg, "neutral")
        assert "认真回应" in result

    def test_help_keywords(self):
        for kw in ["帮", "帮我", "请问", "怎么"]:
            result = _build_depth_hint(f"{kw}我一下", "neutral")
            assert "方案" in result

    def test_happy_keywords(self):
        result = _build_depth_hint("哈哈太好笑了", "neutral")
        assert "开心" in result

    def test_no_hints_neutral(self):
        """普通中等长度消息 + 中性情绪 → 无提示。"""
        result = _build_depth_hint("今天吃了个苹果", "neutral")
        assert result == ""

    def test_neutral_emotion_no_hint(self):
        result = _build_depth_hint("随便聊聊", "neutral")
        # 中性情绪不触发情绪提示
        assert "温柔" not in result


# ═══════════════════════════════════════════════════════════════
# _parse_dsml_tool_calls — DSML 工具调用解析
# ═══════════════════════════════════════════════════════════════


class TestParseDsmlToolCalls:
    def test_empty_string(self):
        assert _parse_dsml_tool_calls("") == []

    def test_no_tool_calls(self):
        assert _parse_dsml_tool_calls("普通文本") == []

    def test_single_tool_call(self):
        text = '<｜｜DSML｜｜invoke name="weather"><｜｜DSML｜｜parameter name="city">北京</｜｜DSML｜｜parameter></｜｜DSML｜｜invoke>'
        result = _parse_dsml_tool_calls(text)
        assert len(result) == 1
        assert result[0]["name"] == "weather"
        assert result[0]["args"]["city"] == "北京"

    def test_multiple_parameters(self):
        text = (
            '<｜｜DSML｜｜invoke name="search">'
            '<｜｜DSML｜｜parameter name="query">天气</｜｜DSML｜｜parameter>'
            '<｜｜DSML｜｜parameter name="limit">5</｜｜DSML｜｜parameter>'
            '</｜｜DSML｜｜invoke>'
        )
        result = _parse_dsml_tool_calls(text)
        assert len(result) == 1
        assert result[0]["name"] == "search"
        assert result[0]["args"]["query"] == "天气"
        assert result[0]["args"]["limit"] == 5  # 数字应被解析为 int

    def test_multiple_tool_calls(self):
        text = (
            '<｜｜DSML｜｜invoke name="a"><｜｜DSML｜｜parameter name="x">1</｜｜DSML｜｜parameter></｜｜DSML｜｜invoke>'
            '<｜｜DSML｜｜invoke name="b"><｜｜DSML｜｜parameter name="y">2</｜｜DSML｜｜parameter></｜｜DSML｜｜invoke>'
        )
        result = _parse_dsml_tool_calls(text)
        assert len(result) == 2
        assert result[0]["name"] == "a"
        assert result[1]["name"] == "b"

    def test_no_parameters(self):
        text = '<｜｜DSML｜｜invoke name="ping"></｜｜DSML｜｜invoke>'
        result = _parse_dsml_tool_calls(text)
        assert len(result) == 1
        assert result[0]["name"] == "ping"
        assert result[0]["args"] == {}


# ═══════════════════════════════════════════════════════════════
# _apply_background_update — 背景更新
# ═══════════════════════════════════════════════════════════════


class TestApplyBackgroundUpdate:
    @patch("api.chat_tasks.get_config", return_value="")
    @patch("api.chat_tasks.set_config")
    def test_dict_add_new_key(self, mock_set, mock_get):
        _apply_background_update({"action": "add", "key": "mood", "value": "happy"})
        mock_set.assert_called_once()
        saved = json.loads(mock_set.call_args[0][1])
        assert saved["mood"] == "happy"

    @patch("api.chat_tasks.get_config", return_value='{"mood": "sad"}')
    @patch("api.chat_tasks.set_config")
    def test_dict_replace(self, mock_set, mock_get):
        _apply_background_update({"action": "replace", "key": "mood", "value": "happy"})
        saved = json.loads(mock_set.call_args[0][1])
        assert saved["mood"] == "happy"

    @patch("api.chat_tasks.get_config", return_value='{"mood": "sad", "age": "20"}')
    @patch("api.chat_tasks.set_config")
    def test_dict_remove(self, mock_set, mock_get):
        _apply_background_update({"action": "remove", "key": "mood"})
        saved = json.loads(mock_set.call_args[0][1])
        assert "mood" not in saved
        assert "age" in saved

    @patch("api.chat_tasks.get_config", return_value='{"mood": "happy"}')
    @patch("api.chat_tasks.set_config")
    def test_dict_same_value_no_write(self, mock_set, mock_get):
        """相同值不应触发写入。"""
        _apply_background_update({"action": "add", "key": "mood", "value": "happy"})
        mock_set.assert_not_called()

    def test_none_no_op(self):
        """None 输入不应做任何操作。"""
        with patch("api.chat_tasks.set_config") as mock_set:
            _apply_background_update(None)
            mock_set.assert_not_called()

    def test_empty_string_no_op(self):
        with patch("api.chat_tasks.set_config") as mock_set:
            _apply_background_update("")
            mock_set.assert_not_called()

    @patch("api.chat_tasks.get_config", return_value="")
    @patch("api.chat_tasks.set_config")
    def test_dict_empty_key_no_op(self, mock_set, mock_get):
        """空 key 不应写入。"""
        _apply_background_update({"action": "add", "key": "", "value": "x"})
        mock_set.assert_not_called()

    @patch("api.chat_tasks.get_config", return_value="")
    @patch("api.chat_tasks.set_config")
    def test_string_background(self, mock_set, mock_get):
        """字符串形式的背景更新。"""
        _apply_background_update("用户喜欢猫")
        mock_set.assert_called_once()
        saved = json.loads(mock_set.call_args[0][1])
        assert any("用户喜欢猫" in v for v in saved.values())

    @patch("api.chat_tasks.get_config", return_value='{"text_0": "用户喜欢猫"}')
    @patch("api.chat_tasks.set_config")
    def test_string_duplicate_no_write(self, mock_set, mock_get):
        """重复字符串不应写入。"""
        _apply_background_update("用户喜欢猫")
        mock_set.assert_not_called()


# ═══════════════════════════════════════════════════════════════
# REMINDER_RULES — 提醒规则配置
# ═══════════════════════════════════════════════════════════════


class TestReminderRules:
    def test_all_levels_have_name(self):
        for level, rule in REMINDER_RULES.items():
            assert "name" in rule, f"Level {level} missing name"

    def test_levels_cover_1_to_7(self):
        assert set(REMINDER_RULES.keys()) == {1, 2, 3, 4, 5, 6, 7}

    def test_forced_level_no_advance(self):
        """强制提醒(level 7) 的 advance_minutes 应为 0。"""
        assert REMINDER_RULES[7]["advance_minutes"] == 0

    def test_forced_level_repeat(self):
        """强制提醒应有 repeat_interval。"""
        assert REMINDER_RULES[7]["repeat_interval"] is not None

    def test_daily_no_repeat(self):
        """日常提醒(level 2) 不应重复。"""
        assert REMINDER_RULES[2]["repeat_interval"] is None

    def test_water_no_repeat(self):
        """喝水提醒(level 1) 不应重复。"""
        assert REMINDER_RULES[1]["repeat_interval"] is None


# ═══════════════════════════════════════════════════════════════
# check_reminders — 提醒检查（需 mock DB）
# ═══════════════════════════════════════════════════════════════


class TestCheckReminders:
    @patch("api.chat_tasks.update_reminder_last_reminded")
    @patch("api.chat_tasks.get_reminders")
    def test_empty_reminders(self, mock_get, mock_update):
        mock_get.return_value = []
        from api.chat_tasks import check_reminders
        assert check_reminders() == []

    @patch("api.chat_tasks.update_reminder_last_reminded")
    @patch("api.chat_tasks.get_reminders")
    def test_done_reminder_skipped(self, mock_get, mock_update):
        mock_get.return_value = [
            {"id": 1, "done": True, "level": 4, "target_time": "2026-06-13T10:00:00", "content": "test"}
        ]
        from api.chat_tasks import check_reminders
        assert check_reminders() == []

    @patch("api.chat_tasks.update_reminder_last_reminded")
    @patch("api.chat_tasks.get_reminders")
    def test_invalid_time_skipped(self, mock_get, mock_update):
        mock_get.return_value = [
            {"id": 1, "done": False, "level": 4, "target_time": "invalid", "content": "test"}
        ]
        from api.chat_tasks import check_reminders
        assert check_reminders() == []

    @patch("api.chat_tasks.update_reminder_last_reminded")
    @patch("api.chat_tasks.get_reminders")
    @patch("api.chat_tasks.datetime")
    def test_future_reminder_within_advance(self, mock_dt, mock_get, mock_update):
        """未来提醒但在提前通知范围内。"""
        now = datetime(2026, 6, 13, 10, 0, 0)
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        # level 4: advance_minutes = 5*24*60 = 7200 (5天)
        target = now + timedelta(days=2)  # 2天后，在5天范围内
        mock_get.return_value = [
            {"id": 1, "done": False, "level": 4, "target_time": target.isoformat(), "content": "测试", "last_reminded": None}
        ]
        from api.chat_tasks import check_reminders
        results = check_reminders()
        assert len(results) == 1
        assert results[0]["id"] == 1
        mock_update.assert_called_once()

    @patch("api.chat_tasks.update_reminder_last_reminded")
    @patch("api.chat_tasks.get_reminders")
    @patch("api.chat_tasks.datetime")
    def test_future_reminder_outside_advance(self, mock_dt, mock_get, mock_update):
        """未来提醒但不在提前通知范围内。"""
        now = datetime(2026, 6, 13, 10, 0, 0)
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        # level 4: advance_minutes = 5*24*60 = 7200 (5天)
        target = now + timedelta(days=10)  # 10天后，超出5天范围
        mock_get.return_value = [
            {"id": 1, "done": False, "level": 4, "target_time": target.isoformat(), "content": "测试", "last_reminded": None}
        ]
        from api.chat_tasks import check_reminders
        results = check_reminders()
        assert len(results) == 0