"""test_chat_tasks.py — api.chat_tasks 纯函数 + 逻辑测试"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from api.chat_tasks import (
    _clean_dsml,
    _apply_background_update,
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
# DepthHintPipe — 深度提示（替代旧的 _build_depth_hint）
# ═══════════════════════════════════════════════════════════════


class TestDepthHintPipe:
    def pipe_result(self, msg, emotion):
        from core.prompt_pipeline import DepthHintPipe, PipelineContext
        pipe = DepthHintPipe()
        ctx = PipelineContext(user_message=msg, emotion=emotion, modules_enabled={"depth_hint": True})
        return pipe.process(ctx) or ""

    def test_empty_message(self):
        result = self.pipe_result("", "neutral")
        assert "短" in result or result == ""

    def test_negative_emotion(self):
        result = self.pipe_result("我今天好难过啊", "negative")
        assert "温柔" in result

    def test_positive_emotion(self):
        result = self.pipe_result("今天天气真好", "positive")
        assert "活跃" in result

    def test_short_message(self):
        result = self.pipe_result("嗯", "neutral")
        assert "短" in result

    def test_long_message(self):
        msg = "这是一段很长很长的消息" * 10
        result = self.pipe_result(msg, "neutral")
        assert "认真回应" in result

    def test_help_keywords(self):
        for kw in ["帮", "帮我", "请问", "怎么"]:
            result = self.pipe_result(f"{kw}我一下", "neutral")
            assert "方案" in result

    def test_happy_keywords(self):
        result = self.pipe_result("哈哈太好笑了", "neutral")
        assert "开心" in result

    def test_no_hints_neutral(self):
        result = self.pipe_result("今天吃了个苹果", "neutral")
        assert result == ""

    def test_neutral_emotion_no_hint(self):
        result = self.pipe_result("随便聊聊", "neutral")
        assert "温柔" not in result


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


