"""test_chat_commands_ex.py — 补充 api.chat_commands 的 handle_welcome/tease/reroll 测试"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock
from datetime import datetime, timedelta

anyio = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _mock_heavy_imports(monkeypatch):
    """阻止重量级导入（LLM、greeting 等）。"""
    for mod in ["api.chat_tasks", "api.greeting"]:
        monkeypatch.setattr(mod, MagicMock(), raising=False)


@pytest.fixture
def mock_ws():
    """记录发送消息的 mock WebSocket。"""
    ws = AsyncMock()
    ws.sent = []

    async def _capture(msg):
        ws.sent.append(msg)

    ws.send_text = AsyncMock(side_effect=_capture)
    return ws


def _get_all_messages(ws):
    """提取所有已发送的 JSON 消息。"""
    results = []
    for raw in ws.sent:
        try:
            results.append(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            pass
    return results


def _get_by_type(ws, msg_type):
    """按 type 过滤消息。"""
    return [m for m in _get_all_messages(ws) if m.get("type") == msg_type]


# ═══════════════════════════════════════════════════════════════
# handle_welcome — /welcome 命令
# ═══════════════════════════════════════════════════════════════


class TestHandleWelcome:
    @anyio
    async def test_welcome_sends_greeting(self, mock_ws):
        from api.chat_commands import handle_welcome

        with patch("api.chat_commands.generate_greeting", return_value="欢迎回来呀～"), \
             patch("api.chat_commands.add_chat_message"), \
             patch("api.chat_commands.save_last_welcome"), \
             patch("api.chat_tasks._clean_dsml", side_effect=lambda x: x):
            await handle_welcome(mock_ws)

        greetings = _get_by_type(mock_ws, "greeting")
        assert len(greetings) == 1
        assert greetings[0]["content"] == "欢迎回来呀～"

    @anyio
    async def test_welcome_sends_done(self, mock_ws):
        from api.chat_commands import handle_welcome

        with patch("api.chat_commands.generate_greeting", return_value="hi"), \
             patch("api.chat_commands.add_chat_message"), \
             patch("api.chat_commands.save_last_welcome"), \
             patch("api.chat_tasks._clean_dsml", side_effect=lambda x: x):
            await handle_welcome(mock_ws)

        dones = _get_by_type(mock_ws, "done")
        assert len(dones) == 1

    @anyio
    async def test_welcome_no_greeting_fallback(self, mock_ws):
        from api.chat_commands import handle_welcome

        with patch("api.chat_commands.generate_greeting", return_value=None):
            await handle_welcome(mock_ws)

        tokens = _get_by_type(mock_ws, "token")
        assert len(tokens) >= 1
        assert "欢迎回来" in tokens[0]["content"]

    @anyio
    async def test_welcome_exception_fallback(self, mock_ws):
        from api.chat_commands import handle_welcome

        with patch("api.chat_commands.generate_greeting", side_effect=Exception("LLM down")):
            await handle_welcome(mock_ws)

        tokens = _get_by_type(mock_ws, "token")
        assert any("生成失败" in t["content"] for t in tokens)


# ═══════════════════════════════════════════════════════════════
# handle_tease — /tease 命令
# ═══════════════════════════════════════════════════════════════


class TestHandleTease:
    @anyio
    async def test_tease_sends_reply(self, mock_ws):
        from api.chat_commands import handle_tease

        with patch("api.chat_commands.get_config", return_value=30), \
             patch("api.chat_commands.set_config"), \
             patch("api.chat_commands.generate_tease", return_value="哼，又来烦我"):
            await handle_tease(mock_ws)

        tokens = _get_by_type(mock_ws, "token")
        assert any("哼" in t["content"] for t in tokens)

    @anyio
    async def test_tease_restores_probability(self, mock_ws):
        from api.chat_commands import handle_tease

        with patch("api.chat_commands.get_config", return_value=30) as mock_get, \
             patch("api.chat_commands.set_config") as mock_set, \
             patch("api.chat_commands.generate_tease", return_value="test"):
            await handle_tease(mock_ws)

        # 最后一次 set_config 应该恢复原始概率
        calls = mock_set.call_args_list
        assert any("30" in str(c) for c in calls)

    @anyio
    async def test_tease_null_fallback(self, mock_ws):
        from api.chat_commands import handle_tease

        with patch("api.chat_commands.get_config", return_value=30), \
             patch("api.chat_commands.set_config"), \
             patch("api.chat_commands.generate_tease", return_value=None):
            await handle_tease(mock_ws)

        tokens = _get_by_type(mock_ws, "token")
        assert any("生成失败" in t["content"] for t in tokens)

    @anyio
    async def test_tease_exception_fallback(self, mock_ws):
        from api.chat_commands import handle_tease

        with patch("api.chat_commands.get_config", return_value=30), \
             patch("api.chat_commands.set_config"), \
             patch("api.chat_commands.generate_tease", side_effect=Exception("boom")):
            await handle_tease(mock_ws)

        tokens = _get_by_type(mock_ws, "token")
        assert any("出错" in t["content"] for t in tokens)

    @anyio
    async def test_tease_sends_done(self, mock_ws):
        from api.chat_commands import handle_tease

        with patch("api.chat_commands.get_config", return_value=30), \
             patch("api.chat_commands.set_config"), \
             patch("api.chat_commands.generate_tease", return_value="x"):
            await handle_tease(mock_ws)

        dones = _get_by_type(mock_ws, "done")
        assert len(dones) == 1


# ═══════════════════════════════════════════════════════════════
# handle_reroll — /reroll 命令
# ═══════════════════════════════════════════════════════════════


class TestHandleReroll:
    @anyio
    async def test_reroll_success(self, mock_ws):
        from api.chat_commands import handle_reroll

        with patch("api.chat_commands.reroll_last_ai_message", return_value="上一条用户消息"):
            user_msg, should_continue = await handle_reroll(mock_ws)

        assert user_msg == "上一条用户消息"
        assert should_continue is False
        reroll_starts = _get_by_type(mock_ws, "reroll_start")
        assert len(reroll_starts) == 1

    @anyio
    async def test_reroll_no_messages(self, mock_ws):
        from api.chat_commands import handle_reroll

        with patch("api.chat_commands.reroll_last_ai_message", return_value=None):
            user_msg, should_continue = await handle_reroll(mock_ws)

        assert user_msg is None
        assert should_continue is True
        tokens = _get_by_type(mock_ws, "token")
        assert any("没有" in t["content"] for t in tokens)

    @anyio
    async def test_reroll_exception(self, mock_ws):
        from api.chat_commands import handle_reroll

        with patch("api.chat_commands.reroll_last_ai_message", side_effect=Exception("db error")):
            user_msg, should_continue = await handle_reroll(mock_ws)

        assert user_msg is None
        assert should_continue is True
        tokens = _get_by_type(mock_ws, "token")
        assert any("出错" in t["content"] for t in tokens)

    @anyio
    async def test_reroll_sends_done_on_failure(self, mock_ws):
        from api.chat_commands import handle_reroll

        with patch("api.chat_commands.reroll_last_ai_message", return_value=None):
            await handle_reroll(mock_ws)

        dones = _get_by_type(mock_ws, "done")
        assert len(dones) == 1


# ═══════════════════════════════════════════════════════════════
# handle_reroll_from — /reroll_from:<id> 命令
# ═══════════════════════════════════════════════════════════════


class TestHandleRerollFrom:
    @anyio
    async def test_reroll_from_success(self, mock_ws):
        from api.chat_commands import handle_reroll_from

        with patch("api.chat_commands.reroll_from_message", return_value="用户消息"):
            user_msg, should_continue = await handle_reroll_from(mock_ws, 42)

        assert user_msg == "用户消息"
        assert should_continue is False
        reroll_starts = _get_by_type(mock_ws, "reroll_start")
        assert len(reroll_starts) == 1
        assert "此处" in reroll_starts[0]["content"]

    @anyio
    async def test_reroll_from_not_found(self, mock_ws):
        from api.chat_commands import handle_reroll_from

        with patch("api.chat_commands.reroll_from_message", return_value=None):
            user_msg, should_continue = await handle_reroll_from(mock_ws, 999)

        assert user_msg is None
        assert should_continue is True
        tokens = _get_by_type(mock_ws, "token")
        assert any("无法" in t["content"] for t in tokens)
        assert any("999" in t["content"] for t in tokens)

    @anyio
    async def test_reroll_from_exception(self, mock_ws):
        from api.chat_commands import handle_reroll_from

        with patch("api.chat_commands.reroll_from_message", side_effect=Exception("db error")):
            user_msg, should_continue = await handle_reroll_from(mock_ws, 1)

        assert user_msg is None
        assert should_continue is True
        tokens = _get_by_type(mock_ws, "token")
        assert any("出错" in t["content"] for t in tokens)

    @anyio
    async def test_reroll_from_sends_done_on_failure(self, mock_ws):
        from api.chat_commands import handle_reroll_from

        with patch("api.chat_commands.reroll_from_message", return_value=None):
            await handle_reroll_from(mock_ws, 1)

        dones = _get_by_type(mock_ws, "done")
        assert len(dones) == 1

