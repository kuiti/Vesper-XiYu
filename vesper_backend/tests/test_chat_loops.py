"""test_chat_loops.py — api.chat_loops 测试"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

anyio = pytest.mark.anyio


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
             patch("api.chat_loops.get_config", return_value="夕语"), \
             patch("api.chat_loops.asyncio.sleep", side_effect=_sleep_then_cancel), \
             patch("api.chat_loops.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 6, 13, 22, 59, 0)
            mock_dt.fromisoformat = datetime.fromisoformat
            with pytest.raises(asyncio.CancelledError):
                await diary_scheduler()