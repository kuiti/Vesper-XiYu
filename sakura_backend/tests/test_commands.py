"""Tests for api.chat_commands.handle_remind time parsing logic."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

# anyio 已安装且有 pytest 插件，用 @pytest.mark.anyio 代替 pytest-asyncio
anyio = pytest.mark.anyio


# We patch dependencies at module level to avoid import side effects
@pytest.fixture(autouse=True)
def _mock_heavy_imports(monkeypatch):
    """Prevent heavy imports (LLM, greeting, etc.) from loading."""
    for mod in [
        "api.chat_tasks", "api.greeting",
    ]:
        monkeypatch.setattr(mod, MagicMock(), raising=False)


@pytest.fixture
def mock_ws():
    """A mock WebSocket that records sent messages."""
    ws = AsyncMock()
    ws.sent = []

    async def _capture(msg):
        ws.sent.append(msg)

    ws.send_text = AsyncMock(side_effect=_capture)
    return ws


def _get_sent_texts(ws):
    """Extract content strings from captured websocket sends."""
    import json
    results = []
    for raw in ws.sent:
        try:
            data = json.loads(raw)
            if data.get("type") == "token":
                results.append(data["content"])
        except (json.JSONDecodeError, TypeError):
            pass
    return results


# ─── 时间解析测试 ───────────────────────────────────────────────


class TestMinutesLater:
    """N分钟后 格式。"""

    @anyio
    async def test_30_minutes_later(self, mock_ws):
        from api.chat_commands import handle_remind

        with patch("api.chat_commands.add_reminder") as mock_add, \
             patch("api.chat_commands.get_reminders", return_value=[]):
            await handle_remind(mock_ws, "/remind 30分钟后 吃药")

        mock_add.assert_called_once()
        iso_str = mock_add.call_args[0][1]
        target = datetime.fromisoformat(iso_str)
        now = datetime.now()
        diff = (target - now).total_seconds()
        # 应该大约 30 分钟后（允许 5 秒误差）
        assert 1795 <= diff <= 1805

    @anyio
    async def test_5_minutes_later(self, mock_ws):
        from api.chat_commands import handle_remind

        with patch("api.chat_commands.add_reminder") as mock_add, \
             patch("api.chat_commands.get_reminders", return_value=[]):
            await handle_remind(mock_ws, "/remind 5分钟后 喝水")

        iso_str = mock_add.call_args[0][1]
        target = datetime.fromisoformat(iso_str)
        diff = (target - datetime.now()).total_seconds()
        assert 295 <= diff <= 305


class TestTomorrowFormat:
    """明天N点 格式。"""

    @anyio
    async def test_tomorrow_9am(self, mock_ws):
        from api.chat_commands import handle_remind

        with patch("api.chat_commands.add_reminder") as mock_add, \
             patch("api.chat_commands.get_reminders", return_value=[]):
            await handle_remind(mock_ws, "/remind 明天9点 开会")

        iso_str = mock_add.call_args[0][1]
        target = datetime.fromisoformat(iso_str)
        assert target.hour == 9
        assert target.minute == 0
        assert target.date() == (datetime.now() + timedelta(days=1)).date()

    @anyio
    async def test_tomorrow_15(self, mock_ws):
        """明天15点（24小时制）。"""
        from api.chat_commands import handle_remind

        with patch("api.chat_commands.add_reminder") as mock_add, \
             patch("api.chat_commands.get_reminders", return_value=[]):
            await handle_remind(mock_ws, "/remind 明天15点 跑步")

        iso_str = mock_add.call_args[0][1]
        target = datetime.fromisoformat(iso_str)
        assert target.hour == 15
        assert target.date() == (datetime.now() + timedelta(days=1)).date()


class TestDayAfterTomorrow:
    """后天N点 格式。"""

    @anyio
    async def test_day_after_tomorrow(self, mock_ws):
        from api.chat_commands import handle_remind

        with patch("api.chat_commands.add_reminder") as mock_add, \
             patch("api.chat_commands.get_reminders", return_value=[]):
            await handle_remind(mock_ws, "/remind 后天10点 面试")

        iso_str = mock_add.call_args[0][1]
        target = datetime.fromisoformat(iso_str)
        assert target.hour == 10
        assert target.date() == (datetime.now() + timedelta(days=2)).date()


class TestAfternoonFormat:
    """下午N点 格式。"""

    @anyio
    async def test_afternoon_3pm(self, mock_ws):
        """下午3点 → 15:00"""
        from api.chat_commands import handle_remind

        with patch("api.chat_commands.add_reminder") as mock_add, \
             patch("api.chat_commands.get_reminders", return_value=[]):
            await handle_remind(mock_ws, "/remind 下午3点 喝下午茶")

        iso_str = mock_add.call_args[0][1]
        target = datetime.fromisoformat(iso_str)
        assert target.hour == 15

    @anyio
    async def test_evening(self, mock_ws):
        """晚上8点 → 20:00"""
        from api.chat_commands import handle_remind

        with patch("api.chat_commands.add_reminder") as mock_add, \
             patch("api.chat_commands.get_reminders", return_value=[]):
            await handle_remind(mock_ws, "/remind 晚上8点 看电影")

        iso_str = mock_add.call_args[0][1]
        target = datetime.fromisoformat(iso_str)
        assert target.hour == 20


class TestCombinedFormat:
    """明天下午N点 组合格式。"""

    @anyio
    async def test_tomorrow_afternoon(self, mock_ws):
        from api.chat_commands import handle_remind

        with patch("api.chat_commands.add_reminder") as mock_add, \
             patch("api.chat_commands.get_reminders", return_value=[]):
            await handle_remind(mock_ws, "/remind 明天下午3点 打羽毛球")

        iso_str = mock_add.call_args[0][1]
        target = datetime.fromisoformat(iso_str)
        assert target.hour == 15
        assert target.date() == (datetime.now() + timedelta(days=1)).date()

    @anyio
    async def test_tomorrow_morning(self, mock_ws):
        from api.chat_commands import handle_remind

        with patch("api.chat_commands.add_reminder") as mock_add, \
             patch("api.chat_commands.get_reminders", return_value=[]):
            await handle_remind(mock_ws, "/remind 明天上午8点 起床")

        iso_str = mock_add.call_args[0][1]
        target = datetime.fromisoformat(iso_str)
        assert target.hour == 8
        assert target.date() == (datetime.now() + timedelta(days=1)).date()


class TestAutoPushToTomorrow:
    """今日已过时间 → 自动推到明天。"""

    @anyio
    async def test_past_time_pushes_to_tomorrow(self, mock_ws):
        """指定一个已经过去的时间，应自动推到明天。"""
        from api.chat_commands import handle_remind

        # 用一个肯定已过的时间：凌晨 1 点（当前下午肯定已过）
        with patch("api.chat_commands.add_reminder") as mock_add, \
             patch("api.chat_commands.get_reminders", return_value=[]), \
             patch("api.chat_commands.datetime") as mock_dt:
            # 让 now() 返回一个固定时间，这样 1 点一定在它前面
            fixed_now = datetime(2026, 6, 12, 15, 0, 0)
            mock_dt.now.return_value = fixed_now
            mock_dt.fromisoformat = datetime.fromisoformat
            # replace 需要代理到真实的 datetime
            original_replace = datetime.replace

            def _replace(self, *args, **kwargs):
                return original_replace(self, *args, **kwargs)

            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            # 让 timedelta 正常工作
            with patch("api.chat_commands.timedelta", timedelta):
                await handle_remind(mock_ws, "/remind 1点 起床")

        iso_str = mock_add.call_args[0][1]
        target = datetime.fromisoformat(iso_str)
        # 应该是明天 1 点
        assert target.day == 13  # fixed_now 是 12 号
        assert target.hour == 1


class TestEdgeCases:
    """边缘情况。"""

    @anyio
    async def test_no_args(self, mock_ws):
        """无参数 → 用法提示。"""
        from api.chat_commands import handle_remind

        await handle_remind(mock_ws, "/remind")
        sent = _get_sent_texts(mock_ws)
        assert any("用法" in s for s in sent)

    @anyio
    async def test_no_args_empty(self, mock_ws):
        """空参数 → 用法提示。"""
        from api.chat_commands import handle_remind

        await handle_remind(mock_ws, "/remind   ")
        sent = _get_sent_texts(mock_ws)
        assert any("用法" in s for s in sent)

    @anyio
    async def test_invalid_time(self, mock_ws):
        """无法识别的时间 → 错误提示。"""
        from api.chat_commands import handle_remind

        await handle_remind(mock_ws, "/remind 随便什么 做什么")
        sent = _get_sent_texts(mock_ws)
        assert any("无法识别" in s for s in sent)

    @anyio
    async def test_empty_content_uses_default(self, mock_ws):
        """只有时间没有内容 → 默认提醒事项。"""
        from api.chat_commands import handle_remind

        with patch("api.chat_commands.add_reminder") as mock_add, \
             patch("api.chat_commands.get_reminders", return_value=[]):
            await handle_remind(mock_ws, "/remind 明天9点")

        # 应该被调用，且内容为默认值
        mock_add.assert_called_once()
        content = mock_add.call_args[0][0]
        assert content == "提醒事项"

    @anyio
    async def test_add_reminder_called_with_correct_args(self, mock_ws):
        """验证 add_reminder 被正确调用。"""
        from api.chat_commands import handle_remind

        with patch("api.chat_commands.add_reminder") as mock_add, \
             patch("api.chat_commands.get_reminders", return_value=[]):
            await handle_remind(mock_ws, "/remind 明天9点 记得吃药")

        mock_add.assert_called_once()
        args = mock_add.call_args[0]
        # args: (content, iso_time, priority=4)
        assert args[0] == "记得吃药"
        assert isinstance(args[1], str)  # ISO format string
        assert args[2] == 4  # priority