"""Tests for core.tag_parser — Tag 指令解析器 + 执行器 + 工具函数"""

import pytest
from unittest.mock import patch, MagicMock
from core.tag_parser import TagParser, TagExecutor, parse_interval, process_reply_tags


# ═══════════════════════════════════════════════════════════════
# TagParser.parse — 标签解析
# ═══════════════════════════════════════════════════════════════


class TestTagParserParse:
    """TagParser.parse() 解析文本中的标签。"""

    def test_parse_add_tag(self):
        result = TagParser.parse("你好<add:用户喜欢猫>")
        assert len(result) == 1
        assert result[0]["type"] == "add"
        assert result[0]["content"] == "用户喜欢猫"

    def test_parse_search_tag(self):
        result = TagParser.parse("<search:猫咪>")
        assert len(result) == 1
        assert result[0]["type"] == "search"
        assert result[0]["content"] == "猫咪"

    def test_parse_note_tag(self):
        result = TagParser.parse("<note:明天有考试>")
        assert len(result) == 1
        assert result[0]["type"] == "note"
        assert result[0]["content"] == "明天有考试"

    def test_parse_todo_tag(self):
        result = TagParser.parse("<todo:买菜>")
        assert len(result) == 1
        assert result[0]["type"] == "todo"
        assert result[0]["content"] == "买菜"

    def test_parse_proactive_tag(self):
        result = TagParser.parse("<proactive:check_weather>")
        assert len(result) == 1
        assert result[0]["type"] == "proactive"
        assert result[0]["content"] == "check_weather"

    def test_parse_multiple_tags(self):
        text = "你好<add:喜欢猫>今天<search:天气>不错<note:记得带伞>"
        result = TagParser.parse(text)
        assert len(result) == 3
        types = [r["type"] for r in result]
        assert "add" in types
        assert "search" in types
        assert "note" in types

    def test_parse_no_tags(self):
        result = TagParser.parse("这是一段普通文本，没有标签")
        assert result == []

    def test_parse_empty_string(self):
        result = TagParser.parse("")
        assert result == []

    def test_parse_whitespace_in_content(self):
        result = TagParser.parse("<add:  用户喜欢猫  >")
        assert len(result) == 1
        # content 应该被 strip
        assert result[0]["content"] == "用户喜欢猫"

    def test_parse_nested_angle_brackets(self):
        """标签内容中的尖括号不应影响解析（非贪婪匹配）。"""
        result = TagParser.parse("<add:用户说<你好>>")
        # 非贪婪匹配 .+? 会匹配到第一个 >
        assert len(result) == 1
        assert result[0]["content"] == "用户说<你好"

    def test_parse_duplicate_tag_types(self):
        text = "<add:事实1><add:事实2>"
        result = TagParser.parse(text)
        assert len(result) == 2
        assert all(r["type"] == "add" for r in result)
        assert result[0]["content"] == "事实1"
        assert result[1]["content"] == "事实2"


# ═══════════════════════════════════════════════════════════════
# TagParser.strip_tags — 标签移除
# ═══════════════════════════════════════════════════════════════


class TestTagParserStripTags:
    """TagParser.strip_tags() 移除标签保留纯文本。"""

    def test_strip_single_tag(self):
        result = TagParser.strip_tags("你好<add:喜欢猫>世界")
        assert result == "你好世界"

    def test_strip_multiple_tags(self):
        result = TagParser.strip_tags("开头<add:事实><search:关键词><note:笔记>结尾")
        assert result == "开头结尾"

    def test_strip_no_tags(self):
        result = TagParser.strip_tags("纯文本没有标签")
        assert result == "纯文本没有标签"

    def test_strip_empty_string(self):
        result = TagParser.strip_tags("")
        assert result == ""

    def test_strip_collapses_triple_newlines(self):
        result = TagParser.strip_tags("第一行<add:删除>\n\n\n\n第二行")
        # 3+ 连续换行应被压缩为 2 个
        assert "\n\n\n" not in result

    def test_strip_only_tags(self):
        result = TagParser.strip_tags("<add:只有标签>")
        assert result == ""

    def test_strip_preserves_single_newlines(self):
        result = TagParser.strip_tags("第一行\n<add:删除>\n第二行")
        assert "第一行" in result
        assert "第二行" in result


# ═══════════════════════════════════════════════════════════════
# TagExecutor — 标签执行
# ═══════════════════════════════════════════════════════════════


class TestTagExecutorExecute:
    """TagExecutor.execute() 分发执行。"""

    @patch("core.tag_parser.TagExecutor._add")
    def test_execute_add(self, mock_add):
        mock_add.return_value = "已记住"
        result = TagExecutor.execute({"type": "add", "content": "test"})
        mock_add.assert_called_once_with("test")
        assert result == "已记住"

    @patch("core.tag_parser.TagExecutor._search")
    def test_execute_search(self, mock_search):
        mock_search.return_value = "搜索结果"
        result = TagExecutor.execute({"type": "search", "content": "keyword"})
        mock_search.assert_called_once_with("keyword")
        assert result == "搜索结果"

    @patch("core.tag_parser.TagExecutor._note")
    def test_execute_note(self, mock_note):
        mock_note.return_value = None
        result = TagExecutor.execute({"type": "note", "content": "笔记内容"})
        mock_note.assert_called_once_with("笔记内容")
        assert result is None

    @patch("core.tag_parser.TagExecutor._todo")
    def test_execute_todo(self, mock_todo):
        mock_todo.return_value = None
        result = TagExecutor.execute({"type": "todo", "content": "待办事项"})
        mock_todo.assert_called_once_with("待办事项")
        assert result is None

    def test_execute_unknown_type_returns_none(self):
        result = TagExecutor.execute({"type": "unknown", "content": "xxx"})
        assert result is None

    def test_execute_proactive_returns_none(self):
        """proactive 类型没有对应的执行方法，返回 None。"""
        result = TagExecutor.execute({"type": "proactive", "content": "check"})
        assert result is None


class TestTagExecutorExecuteAll:
    """TagExecutor.execute_all() 批量执行。"""

    @patch("core.tag_parser.TagExecutor.execute")
    def test_execute_all_success(self, mock_execute):
        mock_execute.return_value = "ok"
        tags = [
            {"type": "add", "content": "a"},
            {"type": "search", "content": "b"},
        ]
        results = TagExecutor.execute_all(tags)
        assert len(results) == 2
        assert all(r["success"] for r in results)
        assert all(r["feedback"] == "ok" for r in results)

    @patch("core.tag_parser.TagExecutor.execute")
    def test_execute_all_with_failure(self, mock_execute):
        mock_execute.side_effect = [Exception("boom"), "ok"]
        tags = [
            {"type": "add", "content": "a"},
            {"type": "search", "content": "b"},
        ]
        results = TagExecutor.execute_all(tags)
        assert len(results) == 2
        assert results[0]["success"] is False
        assert "boom" in results[0]["feedback"]
        assert results[1]["success"] is True

    def test_execute_all_empty(self):
        results = TagExecutor.execute_all([])
        assert results == []


# ═══════════════════════════════════════════════════════════════
# parse_interval — 时间间隔解析
# ═══════════════════════════════════════════════════════════════


class TestParseInterval:
    """parse_interval() 解析时间间隔字符串。"""

    # ─── 秒 ───
    def test_seconds_s(self):
        assert parse_interval("30s") == 30

    def test_seconds_chinese(self):
        assert parse_interval("30秒") == 30

    def test_seconds_sec(self):
        assert parse_interval("10sec") == 10

    # ─── 分钟 ───
    def test_minutes_min(self):
        assert parse_interval("5min") == 300

    def test_minutes_chinese(self):
        assert parse_interval("10分钟") == 600

    def test_minutes_m(self):
        assert parse_interval("3m") == 180

    # ─── 小时 ───
    def test_hours_h(self):
        assert parse_interval("2h") == 7200

    def test_hours_chinese(self):
        assert parse_interval("1小时") == 3600

    def test_hours_hour(self):
        assert parse_interval("3hour") == 10800

    # ─── 带空格 ───
    def test_with_spaces(self):
        assert parse_interval("  30 min  ") == 1800

    def test_no_space(self):
        assert parse_interval("5min") == 300

    # ─── 无效输入 ───
    def test_empty_string(self):
        assert parse_interval("") is None

    def test_none(self):
        assert parse_interval(None) is None

    def test_invalid_format(self):
        assert parse_interval("abc") is None

    def test_zero_value(self):
        assert parse_interval("0min") is None

    def test_negative_value(self):
        assert parse_interval("-5min") is None

    def test_too_large(self):
        assert parse_interval("99999s") is None  # > 86400

    def test_exactly_86400(self):
        assert parse_interval("86400s") == 86400

    def test_just_over_86400(self):
        assert parse_interval("86401s") is None

    def test_no_number(self):
        assert parse_interval("min") is None


# ═══════════════════════════════════════════════════════════════
# process_reply_tags — 综合处理
# ═══════════════════════════════════════════════════════════════


class TestProcessReplyTags:
    """process_reply_tags() 综合处理标签。"""

    def test_no_tags_returns_none_empty(self):
        cleaned, feedback = process_reply_tags("普通回复，没有标签")
        assert cleaned is None
        assert feedback == []

    @patch("core.tag_parser.TagExecutor.execute_all")
    def test_with_tags_executes(self, mock_exec):
        mock_exec.return_value = [
            {"type": "add", "content": "test", "success": True, "feedback": "已记住"},
        ]
        cleaned, feedback = process_reply_tags("你好<add:test>")
        mock_exec.assert_called_once()
        assert cleaned is not None
        assert "test" not in cleaned or "你好" in cleaned
        assert "已记住" in feedback

    def test_tool_calls_used_skips_execution(self):
        """tool_calls_used=True 时只清理标签不执行。"""
        cleaned, feedback = process_reply_tags("你好<add:fact>", tool_calls_used=True)
        assert cleaned is not None
        assert "<add:" not in cleaned
        assert feedback == []

    def test_tool_calls_used_strips_tags(self):
        cleaned, feedback = process_reply_tags(
            "开头<add:事实>中间<search:关键词>结尾",
            tool_calls_used=True
        )
        assert "开头" in cleaned
        assert "结尾" in cleaned
        assert "<add:" not in cleaned
        assert "<search:" not in cleaned
        assert feedback == []