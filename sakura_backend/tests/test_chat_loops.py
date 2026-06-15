"""test_chat_loops.py — api.chat_loops 测试"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

anyio = pytest.mark.anyio


# ═══════════════════════════════════════════════════════════════
# reminder_loop — 提醒循环
# ═══════════════════════════════════════════════════════════════


class TestReminderLoop:
    @anyio
    async def test_sends_reminder_data(self):
        """当 check_reminders 返回数据时，应通过 WebSocket 发送。"""
        from api.chat_loops import reminder_loop

        ws = AsyncMock()
        ws.sent = []
        reminder_data = [{"id": 1, "content": "吃药", "level_name": "待办"}]

        async def _capture(msg):
            ws.sent.append(msg)
            # 发送后取消任务
            raise asyncio.CancelledError

        ws.send_text = AsyncMock(side_effect=_capture)

        with patch("api.chat_loops.check_reminders", return_value=reminder_data), \
             patch("api.chat_loops.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(asyncio.CancelledError):
                await reminder_loop(ws)

        assert len(ws.sent) == 1
        data = json.loads(ws.sent[0])
        assert data["type"] == "reminder"
        assert data["data"] == reminder_data[0]

    @anyio
    async def test_handles_websocket_disconnect(self):
        """WebSocket 断开时应安静退出。"""
        from api.chat_loops import reminder_loop
        from fastapi import WebSocketDisconnect

        ws = AsyncMock()

        async def _raise_disconnect(delay=0):
            raise WebSocketDisconnect()

        with patch("api.chat_loops.asyncio.sleep", side_effect=_raise_disconnect):
            # 不应抛出异常
            await reminder_loop(ws)

    @anyio
    async def test_handles_check_exception(self):
        """check_reminders 抛异常时不应崩溃。"""
        from api.chat_loops import reminder_loop

        ws = AsyncMock()
        call_count = 0

        async def _sleep_then_cancel(delay):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError

        with patch("api.chat_loops.check_reminders", side_effect=Exception("db error")), \
             patch("api.chat_loops.asyncio.sleep", side_effect=_sleep_then_cancel):
            with pytest.raises(asyncio.CancelledError):
                await reminder_loop(ws)


# ═══════════════════════════════════════════════════════════════
# diary_scheduler — 日记调度
# ═══════════════════════════════════════════════════════════════


class TestDiaryScheduler:
    @anyio
    async def test_skips_when_few_messages(self):
        """消息数 < 5 时跳过日记生成。"""
        from api.chat_loops import diary_scheduler

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"cnt": 2}  # 只有 2 条消息
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        call_count = 0

        async def _sleep_then_cancel(delay):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError

        with patch("api.chat_loops.get_conn", return_value=MagicMock(__enter__=MagicMock(return_value=mock_conn), __exit__=MagicMock(return_value=False))), \
             patch("api.chat_loops.get_config", return_value="佐仓"), \
             patch("api.chat_loops.asyncio.sleep", side_effect=_sleep_then_cancel), \
             patch("api.chat_loops.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 6, 13, 22, 59, 0)
            mock_dt.fromisoformat = datetime.fromisoformat
            with pytest.raises(asyncio.CancelledError):
                await diary_scheduler()