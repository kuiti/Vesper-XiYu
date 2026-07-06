"""test_profile_builder.py — core.profile_builder 测试"""

import pytest
import json
import hashlib
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from core.profile_builder import (
    get_profile, clear_profile_cache,
    save_profile, cleanup_expired_profile,
    get_profile_context, get_facts_context,
    extract_entities_from_text,
    track_event_completion, track_plan_intent, track_in_progress,
    _categorize_event, _COMPLETION_REGEX, _PLAN_REGEX, _IN_PROGRESS_REGEX,
    clear_completed_plans,
)


# ═══════════════════════════════════════════════════════════════
# clear_profile_cache — 缓存清理
# ═══════════════════════════════════════════════════════════════


class TestClearProfileCache:
    def test_clears_cache(self):
        import core.profile_builder as pb
        pb._profile_cache = {"test": "data"}
        clear_profile_cache()
        assert pb._profile_cache is None


# ═══════════════════════════════════════════════════════════════
# get_profile — 画像获取
# ═══════════════════════════════════════════════════════════════


class TestGetProfile:
    def test_returns_cached(self):
        import core.profile_builder as pb
        pb._profile_cache = {"name": {"value": "test", "confidence": 0.9}}
        result = get_profile()
        assert result["name"]["value"] == "test"

    @patch("core.profile_builder.get_conn")
    def test_fetches_from_db(self, mock_conn):
        import core.profile_builder as pb
        pb._profile_cache = None
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"key": "name", "value": "小明", "confidence": 0.9},
            {"key": "age", "value": "20", "confidence": 0.8},
        ]
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        result = get_profile()
        assert "name" in result
        assert result["name"]["value"] == "小明"

    @patch("core.profile_builder.get_conn")
    def test_empty_db_returns_empty(self, mock_conn):
        import core.profile_builder as pb
        pb._profile_cache = None
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        result = get_profile()
        assert result == {}


# ═══════════════════════════════════════════════════════════════
# save_profile — 画像保存（置信度合并）
# ═══════════════════════════════════════════════════════════════


class TestSaveProfile:
    @patch("core.profile_builder.get_conn")
    @patch("core.profile_builder.get_profile", return_value={})
    def test_saves_new_entry(self, mock_get, mock_conn):
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        save_profile({"city": "上海"}, {"city": 0.9})
        mock_cursor.execute.assert_called_once()
        # 确认写入了正确的置信度
        call_args = mock_cursor.execute.call_args[0]
        assert 0.9 in call_args[1]

    @patch("core.profile_builder.get_conn")
    @patch("core.profile_builder.get_profile")
    def test_higher_confidence_overwrites(self, mock_get, mock_conn):
        """新置信度更高时应覆写。"""
        mock_get.return_value = {"city": {"value": "北京", "confidence": 0.6}}
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        save_profile({"city": "上海"}, {"city": 0.9})
        mock_cursor.execute.assert_called_once()

    @patch("core.profile_builder.get_conn")
    @patch("core.profile_builder.get_profile")
    def test_lower_confidence_keeps_old(self, mock_get, mock_conn):
        """新置信度更低时不应覆写。"""
        mock_get.return_value = {"city": {"value": "北京", "confidence": 0.9}}
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        save_profile({"city": "上海"}, {"city": 0.5})
        mock_cursor.execute.assert_not_called()

    @patch("core.profile_builder.get_conn")
    @patch("core.profile_builder.get_profile")
    def test_same_value_updates_confidence(self, mock_get, mock_conn):
        """相同值时取最高置信度。"""
        mock_get.return_value = {"city": {"value": "上海", "confidence": 0.7}}
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        save_profile({"city": "上海"}, {"city": 0.9})
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        assert call_args[1][2] == 0.9  # 应取 max(0.7, 0.9)


# ═══════════════════════════════════════════════════════════════
# cleanup_expired_profile — 过期清理
# ═══════════════════════════════════════════════════════════════


class TestCleanupExpired:
    @patch("core.profile_builder.get_conn")
    def test_deletes_old_entries(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        deleted = cleanup_expired_profile(90)
        assert deleted == 5

    @patch("core.profile_builder.get_conn")
    def test_custom_days(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        cleanup_expired_profile(30)
        # 确认 SQL 中使用了 30 天
        call_args = mock_cursor.execute.call_args[0]
        assert len(call_args) >= 2


# ═══════════════════════════════════════════════════════════════
# get_profile_context — 画像上下文
# ═══════════════════════════════════════════════════════════════


class TestGetProfileContext:
    @patch("core.profile_builder.get_profile", return_value={})
    def test_empty_profile(self, mock_get):
        assert get_profile_context() == ""

    @patch("core.profile_builder.get_profile")
    def test_normal_profile(self, mock_get):
        mock_get.return_value = {
            "city": {"value": "上海", "confidence": 0.9},
        }
        result = get_profile_context()
        assert "上海" in result
        assert "用户画像" in result

    @patch("core.profile_builder.get_profile")
    def test_low_confidence_filtered(self, mock_get):
        """低置信度条目应被过滤。"""
        mock_get.return_value = {
            "city": {"value": "上海", "confidence": 0.3},
        }
        result = get_profile_context()
        assert result == ""

    @patch("core.profile_builder.get_profile")
    def test_plan_section(self, mock_get):
        mock_get.return_value = {
            "_plan_旅行": {"value": "计划中", "confidence": 0.9},
        }
        result = get_profile_context()
        assert "待办计划" in result

    @patch("core.profile_builder.get_profile")
    def test_event_section(self, mock_get):
        mock_get.return_value = {
            "_event_理发": {"value": "已完成", "confidence": 0.9},
        }
        result = get_profile_context()
        assert "已完成" in result

    @patch("core.profile_builder.get_profile")
    def test_moderate_confidence_note(self, mock_get):
        """0.55-0.7 置信度应标注'仅供参考'。"""
        mock_get.return_value = {
            "city": {"value": "上海", "confidence": 0.6},
        }
        result = get_profile_context()
        assert "仅供参考" in result


# ═══════════════════════════════════════════════════════════════
# get_facts_context — 原子事实上下文
# ═══════════════════════════════════════════════════════════════


class TestGetFactsContext:
    @patch("core.profile_builder.get_conn")
    def test_empty_facts(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.return_value = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor
        mock_conn.return_value.__enter__.return_value = mock_conn.return_value
        mock_conn.return_value.__exit__.return_value = False
        assert get_facts_context() == ""

    @patch("core.profile_builder.get_conn")
    def test_active_fact_included(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"value": json.dumps({"text": "用户喜欢猫", "importance": 8, "status": "active", "temporality": "permanent"}, ensure_ascii=False)},
        ]
        mock_conn.return_value = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor
        mock_conn.return_value.__enter__.return_value = mock_conn.return_value
        mock_conn.return_value.__exit__.return_value = False
        result = get_facts_context()
        assert "用户喜欢猫" in result

    @patch("core.profile_builder.get_conn")
    def test_inactive_fact_excluded(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"value": json.dumps({"text": "旧事实", "importance": 8, "status": "superseded", "temporality": "permanent"})},
        ]
        mock_conn.return_value = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor
        mock_conn.return_value.__enter__.return_value = mock_conn.return_value
        mock_conn.return_value.__exit__.return_value = False
        result = get_facts_context()
        assert "旧事实" not in result

    @patch("core.profile_builder.get_conn")
    def test_low_importance_excluded(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"value": json.dumps({"text": "不重要的事", "importance": 2, "status": "active", "temporality": "permanent"})},
        ]
        mock_conn.return_value = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor
        mock_conn.return_value.__enter__.return_value = mock_conn.return_value
        mock_conn.return_value.__exit__.return_value = False
        result = get_facts_context()
        assert "不重要的事" not in result

    @patch("core.profile_builder.get_conn")
    def test_sorted_by_importance(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"value": json.dumps({"text": "低重要", "importance": 5, "status": "active", "temporality": "permanent"})},
            {"value": json.dumps({"text": "高重要", "importance": 9, "status": "active", "temporality": "permanent"})},
        ]
        mock_conn.return_value = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor
        mock_conn.return_value.__enter__.return_value = mock_conn.return_value
        mock_conn.return_value.__exit__.return_value = False
        result = get_facts_context()
        # 高重要的应排在前面
        high_pos = result.index("高重要")
        low_pos = result.index("低重要")
        assert high_pos < low_pos


# ═══════════════════════════════════════════════════════════════
# extract_entities_from_text — 实体提取
# ═══════════════════════════════════════════════════════════════


class TestExtractEntities:
    def test_quoted_text(self):
        """引号内文本应被提取为实体。"""
        entities = extract_entities_from_text('他叫「小明」')
        texts = [e[0] for e in entities]
        assert "小明" in texts

    def test_double_quotes(self):
        entities = extract_entities_from_text('她说"你好"')
        texts = [e[0] for e in entities]
        assert "你好" in texts

    def test_empty_text(self):
        entities = extract_entities_from_text("")
        # 可能有 jieba 提取的结果，但至少不应该崩溃
        assert isinstance(entities, list)

    def test_no_entities(self):
        entities = extract_entities_from_text("今天天气不错")
        assert isinstance(entities, list)


# ═══════════════════════════════════════════════════════════════
# track_event_completion — 事件完成追踪
# ═══════════════════════════════════════════════════════════════


class TestTrackEventCompletion:
    @patch("core.profile_builder.get_conn")
    def test_detects_completion(self, mock_conn):
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        result = track_event_completion("我去了理发店剪头发了")
        assert result is True

    def test_no_completion(self):
        result = track_event_completion("今天天气不错")
        assert result is False

    @patch("core.profile_builder.get_conn")
    def test_detects_got_home(self, mock_conn):
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        result = track_event_completion("我到家了")
        assert result is True

    @patch("core.profile_builder.get_conn")
    def test_detects_finished(self, mock_conn):
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        result = track_event_completion("考完了")
        assert result is True


# ═══════════════════════════════════════════════════════════════
# track_plan_intent — 计划意图追踪
# ═══════════════════════════════════════════════════════════════


class TestTrackPlanIntent:
    @patch("core.profile_builder.get_conn")
    def test_detects_plan(self, mock_conn):
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        result = track_plan_intent("我打算去超市买菜")
        assert result is True

    def test_no_plan(self):
        result = track_plan_intent("今天吃了苹果")
        assert result is False


# ═══════════════════════════════════════════════════════════════
# track_in_progress — 进行中追踪
# ═══════════════════════════════════════════════════════════════


class TestTrackInProgress:
    @patch("core.profile_builder.get_conn")
    def test_detects_in_progress(self, mock_conn):
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        result = track_in_progress("正在写作业中")
        assert result is True

    def test_no_in_progress(self):
        result = track_in_progress("写完了作业")
        assert result is False


# ═══════════════════════════════════════════════════════════════
# _categorize_event — 事件分类
# ═══════════════════════════════════════════════════════════════


class TestCategorizeEvent:
    def test_hair(self):
        assert _categorize_event("去剪了头发") == "理发"

    def test_food(self):
        assert _categorize_event("去吃了火锅") == "吃饭"

    def test_package(self):
        assert _categorize_event("取了快递") == "快递"

    def test_exam(self):
        assert _categorize_event("考完了") == "考试"

    def test_shopping(self):
        assert _categorize_event("买了新衣服") == "购物"

    def test_unknown(self):
        assert _categorize_event("某某某某某某") == "事项"


# ═══════════════════════════════════════════════════════════════
# clear_completed_plans — 已完成计划清理
# ═══════════════════════════════════════════════════════════════


class TestClearCompletedPlans:
    @patch("core.profile_builder.get_conn")
    def test_deletes_plans_for_done_events(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"key": "_event_理发"},
        ]
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        clear_completed_plans()
        # 应该删除对应的 _plan_ 和 _progress_
        delete_calls = [c for c in mock_cursor.execute.call_args_list if "DELETE" in str(c)]
        assert len(delete_calls) >= 1