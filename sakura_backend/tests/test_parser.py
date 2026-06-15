"""Tests for api.chat_parser.ThinkingParser."""

import pytest
from api.chat_parser import ThinkingParser


class TestFeedThinkingState:
    """feed() 在 thinking 状态下的行为。"""

    def test_returns_none_while_thinking(self):
        p = ThinkingParser()
        assert p.feed("我在想") is None
        assert p.feed("一些事情") is None

    def test_switches_to_reply_on_marker(self):
        p = ThinkingParser()
        # 先喂一些思考内容
        p.feed("思考了一下")
        result = p.feed("【回复】你好")
        assert result == "你好"
        assert p.state == "reply"

    def test_returns_none_when_marker_is_at_boundary(self):
        """标记恰好是 token 边界，后续 token 才是回复。"""
        p = ThinkingParser()
        p.feed("思考")
        result = p.feed("【回复】")
        # 标记后没有余量 → None
        assert result is None

    def test_returns_remainder_when_marker_and_content_in_same_token(self):
        p = ThinkingParser()
        result = p.feed("思考【回复】Hello")
        assert result == "Hello"
        assert p.state == "reply"


class TestFeedReplyState:
    """feed() 在 reply 状态下的行为。"""

    def test_returns_each_token(self):
        p = ThinkingParser()
        p.feed("思考【回复】")
        assert p.feed("你") == "你"
        assert p.feed("好") == "好"
        assert p.reply == "你好"

    def test_accumulates_reply(self):
        p = ThinkingParser()
        p.feed("思考【回复】")
        p.feed("AB")
        p.feed("CD")
        assert p.reply == "ABCD"


class TestDSMLFiltering:
    """DSML 工具调用标记的过滤。"""

    def test_dsml_filtered_in_thinking_state(self):
        p = ThinkingParser()
        dsml = '<｜｜DSML｜｜tool_calls>invoke stuff</｜｜DSML｜｜tool_calls>'
        p.feed("思考" + dsml)
        # DSML 被过滤后 buffer 里应该没有它
        assert "DSML" not in p.buffer

    def test_dsml_filtered_in_reply_state(self):
        p = ThinkingParser()
        p.feed("思考【回复】")
        dsml = '<｜｜DSML｜｜tool_calls>invoke stuff</｜｜DSML｜｜tool_calls>'
        result = p.feed(dsml)
        # 遇到 DSML 时不发送内容
        assert result is None
        # reply 中 DSML 被过滤
        assert "DSML" not in p.reply

    def test_dsml_cross_segment(self):
        """DSML 标记跨多个 token。"""
        p = ThinkingParser()
        p.feed("思考【回复】")
        p.feed('<｜｜DSML｜｜tool')
        p.feed('_calls>invoke stuff</｜｜DSML｜｜tool_calls>')
        # 最终 reply 中不应包含 DSML
        assert "DSML" not in p.reply

    def test_double_angle_bracket_filtered(self):
        """<<>> 分隔符在 thinking 状态被过滤。"""
        p = ThinkingParser()
        p.feed("<<>>思考")
        assert "<<" not in p.buffer


class TestFallbackCheck:
    """fallback_check() 的行为。"""

    def test_false_when_small_buffer(self):
        p = ThinkingParser()
        p.feed("短文本")
        assert p.fallback_check() is False

    def test_true_when_large_buffer_no_marker(self):
        p = ThinkingParser()
        p.feed("x" * 1001)
        assert p.fallback_check() is True

    def test_false_when_marker_present(self):
        p = ThinkingParser()
        p.feed("x" * 900 + "【回复】hello")
        assert p.fallback_check() is False

    def test_false_when_in_reply_state(self):
        p = ThinkingParser()
        p.feed("思考【回复】" + "x" * 1001)
        assert p.state == "reply"
        assert p.fallback_check() is False


class TestExtractReplyFromBuffer:
    """extract_reply_from_buffer() 降级提取。"""

    def test_empty_buffer(self):
        p = ThinkingParser()
        assert p.extract_reply_from_buffer() == ""

    def test_single_paragraph(self):
        p = ThinkingParser()
        p.buffer = "这是唯一的段落"
        assert p.extract_reply_from_buffer() == "这是唯一的段落"

    def test_last_paragraph_short_merges_with_previous(self):
        p = ThinkingParser()
        p.buffer = "第一段很长的内容用来测试长度超过二十个字符\n第二段很长的内容也超过二十个字符\n短尾"
        result = p.extract_reply_from_buffer()
        # 最后一段 < 20 字符 → 取倒数第二段 + 最后一段
        assert "第二段" in result
        assert "短尾" in result

    def test_last_paragraph_long_enough(self):
        p = ThinkingParser()
        p.buffer = "第一段很长的内容用来测试长度超过二十个字符\n第二段很长的内容也超过二十个字符且足够长可以独立显示"
        result = p.extract_reply_from_buffer()
        assert result.startswith("第二段")

    def test_dsml_removed_from_buffer(self):
        p = ThinkingParser()
        dsml = '<｜｜DSML｜｜tool_calls>invoke</｜｜DSML｜｜tool_calls>'
        p.buffer = "回复内容" + dsml
        result = p.extract_reply_from_buffer()
        assert "DSML" not in result


class TestExtractDemand:
    """extract_demand() 解析思考内容中的需求层级。"""

    def test_full_demand(self):
        p = ThinkingParser()
        p.thinking = (
            "需求层级：情感支持\n"
            "用户情绪：焦虑\n"
            "深层需求：需要安慰\n"
            "回复策略：温柔共情"
        )
        d = p.extract_demand()
        assert d["level"] == "情感支持"
        assert d["emotion"] == "焦虑"
        assert d["latent"] == "需要安慰"
        assert d["strategy"] == "温柔共情"

    def test_partial_demand(self):
        p = ThinkingParser()
        p.thinking = "需求层级：信息查询\n用户情绪：平静"
        d = p.extract_demand()
        assert d["level"] == "信息查询"
        assert d["emotion"] == "平静"
        assert d["latent"] == ""  # 未找到
        assert d["strategy"] == ""

    def test_no_thinking(self):
        p = ThinkingParser()
        assert p.extract_demand() is None

    def test_colon_full_width(self):
        """全角冒号也能解析。"""
        p = ThinkingParser()
        p.thinking = "需求层级：闲聊"
        d = p.extract_demand()
        assert d["level"] == "闲聊"

    def test_thinking_full_truncated(self):
        p = ThinkingParser()
        p.thinking = "x" * 600
        d = p.extract_demand()
        assert len(d["thinking_full"]) <= 500


class TestEdgeCases:
    """边缘情况。"""

    def test_empty_input(self):
        p = ThinkingParser()
        assert p.feed("") is None
        assert p.state == "thinking"

    def test_only_thinking_no_reply(self):
        p = ThinkingParser()
        p.feed("我在想")
        p.feed("一直在想")
        assert p.state == "thinking"
        assert p.reply == ""

    def test_multiple_replies_not_expected(self):
        """标记只应触发一次状态切换。"""
        p = ThinkingParser()
        p.feed("思考【回复】第一段")
        assert p.state == "reply"
        # 第二个标记应作为普通文本返回
        result = p.feed("【回复】第二段")
        assert result is not None  # 不应该再次吞掉

    def test_marker_in_pieces(self):
        """标记被 token 切断。"""
        p = ThinkingParser()
        assert p.feed("思考【") is None
        assert p.feed("回复】OK") == "OK"
        assert p.state == "reply"