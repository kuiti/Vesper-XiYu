"""test_emotion_evolution.py — core.emotion_evolution 测试"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from core.emotion_evolution import (
    TRAIT_MIN, TRAIT_MAX, TRAIT_DEFAULTS, TRAIT_DESCRIPTIONS,
    get_trait, get_all_traits, update_trait,
    get_trait_profile, get_emotion_timeline,
    _rule_silence_decay, _rule_cold_adaptation,
    _rule_habitual_closeness, _rule_weekly_reflection,
    _get_hours_since_last_interaction, _try_claim_evolution_date,
    _get_last_evolution_date, _set_last_evolution_date,
    process_daily_evolution,
)


# ═══════════════════════════════════════════════════════════════
# 常量检查
# ═══════════════════════════════════════════════════════════════


class TestConstants:
    def test_trait_bounds(self):
        assert TRAIT_MIN == 0.0
        assert TRAIT_MAX == 1.0

    def test_trait_defaults_in_range(self):
        for key, val in TRAIT_DEFAULTS.items():
            assert TRAIT_MIN <= val <= TRAIT_MAX, f"{key}={val} out of range"

    def test_all_five_ocean_traits(self):
        expected = {"openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"}
        assert set(TRAIT_DEFAULTS.keys()) == expected

    def test_trait_descriptions_covers_all(self):
        for key in TRAIT_DEFAULTS:
            assert key in TRAIT_DESCRIPTIONS, f"Missing description for {key}"
            desc = TRAIT_DESCRIPTIONS[key]
            assert "high" in desc
            assert "mid" in desc
            assert "low" in desc


# ═══════════════════════════════════════════════════════════════
# update_trait — 特征更新
# ═══════════════════════════════════════════════════════════════


class TestUpdateTrait:
    @patch("core.emotion_evolution.get_trait", return_value=0.5)
    @patch("core.emotion_evolution.get_conn")
    @patch("core.emotion_evolution._now", return_value="2026-01-01T00:00:00")
    def test_positive_delta(self, mock_now, mock_conn, mock_get):
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        update_trait("openness", 0.1)
        # 应该写入 0.6
        mock_cursor.execute.assert_called_once()
        written_val = mock_cursor.execute.call_args[0][1][0]
        assert abs(written_val - 0.6) < 0.01

    @patch("core.emotion_evolution.get_trait", return_value=0.5)
    @patch("core.emotion_evolution.get_conn")
    @patch("core.emotion_evolution._now", return_value="2026-01-01T00:00:00")
    def test_negative_delta(self, mock_now, mock_conn, mock_get):
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        update_trait("openness", -0.1)
        written_val = mock_cursor.execute.call_args[0][1][0]
        assert abs(written_val - 0.4) < 0.01

    @patch("core.emotion_evolution.get_trait", return_value=0.95)
    @patch("core.emotion_evolution.get_conn")
    @patch("core.emotion_evolution._now", return_value="2026-01-01T00:00:00")
    def test_clamp_at_max(self, mock_now, mock_conn, mock_get):
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        update_trait("openness", 0.2)
        written_val = mock_cursor.execute.call_args[0][1][0]
        assert written_val == TRAIT_MAX

    @patch("core.emotion_evolution.get_trait", return_value=0.05)
    @patch("core.emotion_evolution.get_conn")
    @patch("core.emotion_evolution._now", return_value="2026-01-01T00:00:00")
    def test_clamp_at_min(self, mock_now, mock_conn, mock_get):
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        update_trait("openness", -0.2)
        written_val = mock_cursor.execute.call_args[0][1][0]
        assert written_val == TRAIT_MIN

    @patch("core.emotion_evolution.get_trait", return_value=0.5)
    @patch("core.emotion_evolution.get_conn")
    def test_tiny_delta_no_write(self, mock_conn, mock_get):
        """变化量 < 0.01 时不写入。"""
        update_trait("openness", 0.005)
        mock_conn.assert_not_called()


# ═══════════════════════════════════════════════════════════════
# get_trait / get_all_traits — 特征读取
# ═══════════════════════════════════════════════════════════════


class TestGetTrait:
    @patch("core.emotion_evolution.get_conn")
    def test_get_trait_from_db(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": 0.7}
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        # Reset initialization flag
        import core.emotion_evolution as ee
        ee._traits_initialized = True
        val = get_trait("openness")
        assert val == 0.7

    @patch("core.emotion_evolution.get_conn")
    def test_get_trait_default_when_missing(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        import core.emotion_evolution as ee
        ee._traits_initialized = True
        val = get_trait("openness")
        assert val == TRAIT_DEFAULTS["openness"]

    @patch("core.emotion_evolution.get_conn")
    def test_get_all_traits(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"key": "openness", "value": 0.6},
            {"key": "extraversion", "value": 0.8},
        ]
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=mock_cursor)))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        import core.emotion_evolution as ee
        ee._traits_initialized = True
        result = get_all_traits()
        assert result["openness"] == 0.6
        assert result["extraversion"] == 0.8
        # 未在 DB 中的应使用默认值
        assert result["conscientiousness"] == TRAIT_DEFAULTS["conscientiousness"]


# ═══════════════════════════════════════════════════════════════
# get_trait_profile — 性格画像
# ═══════════════════════════════════════════════════════════════


class TestGetTraitProfile:
    @patch("core.emotion_evolution.get_config", return_value="佐仓")
    @patch("core.emotion_evolution.get_all_traits")
    def test_profile_structure(self, mock_traits, mock_config):
        mock_traits.return_value = {
            "openness": 0.5, "conscientiousness": 0.5,
            "extraversion": 0.5, "agreeableness": 0.5, "neuroticism": 0.5,
        }
        profile = get_trait_profile()
        assert "traits" in profile
        assert "descriptions" in profile
        assert "summary" in profile
        assert len(profile["traits"]) == 5

    @patch("core.emotion_evolution.get_config", return_value="佐仓")
    @patch("core.emotion_evolution.get_all_traits")
    def test_high_extraversion_description(self, mock_traits, mock_config):
        mock_traits.return_value = {
            "openness": 0.5, "conscientiousness": 0.5,
            "extraversion": 0.8, "agreeableness": 0.8, "neuroticism": 0.3,
        }
        profile = get_trait_profile()
        assert "乐观" in profile["summary"] or "活泼" in profile["descriptions"]["extraversion"]

    @patch("core.emotion_evolution.get_config", return_value="佐仓")
    @patch("core.emotion_evolution.get_all_traits")
    def test_low_extraversion_description(self, mock_traits, mock_config):
        mock_traits.return_value = {
            "openness": 0.2, "conscientiousness": 0.2,
            "extraversion": 0.2, "agreeableness": 0.2, "neuroticism": 0.8,
        }
        profile = get_trait_profile()
        assert "悲观" in profile["summary"] or "内向" in profile["descriptions"]["extraversion"]

    @patch("core.emotion_evolution.get_config", return_value="佐仓")
    @patch("core.emotion_evolution.get_all_traits")
    def test_traits_rounded_to_2_decimals(self, mock_traits, mock_config):
        mock_traits.return_value = {
            "openness": 0.555, "conscientiousness": 0.333,
            "extraversion": 0.777, "agreeableness": 0.111, "neuroticism": 0.999,
        }
        profile = get_trait_profile()
        for val in profile["traits"].values():
            assert len(str(val).split(".")[-1]) <= 2


# ═══════════════════════════════════════════════════════════════
# _try_claim_evolution_date — 原子抢占
# ═══════════════════════════════════════════════════════════════


class TestTryClaimEvolutionDate:
    @patch("core.emotion_evolution.set_config")
    @patch("core.emotion_evolution.get_config", return_value="2026-06-12")
    def test_first_run_today_returns_true(self, mock_get, mock_set):
        assert _try_claim_evolution_date("2026-06-13") is True
        mock_set.assert_called_with("last_evolution_date", "2026-06-13")

    @patch("core.emotion_evolution.get_config", return_value="2026-06-13")
    def test_same_day_returns_false(self, mock_get):
        assert _try_claim_evolution_date("2026-06-13") is False


# ═══════════════════════════════════════════════════════════════
# _get_hours_since_last_interaction — 时间计算
# ═══════════════════════════════════════════════════════════════


class TestHoursSinceLastInteraction:
    @patch("core.emotion_evolution.get_config")
    def test_returns_hours(self, mock_get):
        two_hours_ago = (datetime.now() - timedelta(hours=2)).isoformat()
        mock_get.return_value = two_hours_ago
        hours = _get_hours_since_last_interaction()
        assert hours is not None
        assert 1.9 < hours < 2.1

    @patch("core.emotion_evolution.get_config", return_value="")
    def test_empty_returns_none(self, mock_get):
        assert _get_hours_since_last_interaction() is None

    @patch("core.emotion_evolution.get_config", return_value="invalid-date")
    def test_invalid_returns_none(self, mock_get):
        assert _get_hours_since_last_interaction() is None


# ═══════════════════════════════════════════════════════════════
# _rule_silence_decay — 沉默衰减规则
# ═══════════════════════════════════════════════════════════════


class TestRuleSilenceDecay:
    def test_none_hours_no_action(self):
        """hours_since=None 不应做任何操作。"""
        with patch("core.emotion_evolution._update_relationship_value") as mock_update:
            _rule_silence_decay(None)
            mock_update.assert_not_called()

    def test_less_than_3_days_no_action(self):
        """不到 3 天不触发衰减。"""
        with patch("core.emotion_evolution._update_relationship_value") as mock_update:
            _rule_silence_decay(48)  # 2天
            mock_update.assert_not_called()

    @patch("core.emotion_evolution.set_config")
    @patch("core.emotion_evolution._log_evolution_event")
    @patch("core.emotion_evolution.update_trait")
    @patch("core.emotion_evolution._update_relationship_value")
    @patch("core.emotion_evolution._get_last_decay_date", return_value=None)
    def test_3_days_triggers_decay(self, mock_last, mock_rel, mock_trait, mock_log, mock_set):
        """3 天以上沉默应触发衰减。"""
        _rule_silence_decay(72)  # 3天
        # affection -0.2 * 1, trust -0.1 * 1 (first run, days_since_last=1)
        mock_rel.assert_any_call("affection", -0.2)
        mock_rel.assert_any_call("trust", -0.1)
        mock_log.assert_called_once()

    @patch("core.emotion_evolution.set_config")
    @patch("core.emotion_evolution._log_evolution_event")
    @patch("core.emotion_evolution.update_trait")
    @patch("core.emotion_evolution._update_relationship_value")
    @patch("core.emotion_evolution._get_last_decay_date")
    def test_7_plus_days_reduces_initiative(self, mock_last, mock_rel, mock_trait, mock_log, mock_set):
        """7+ 天沉默应降低 initiative。"""
        mock_last.return_value = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d")
        _rule_silence_decay(200)  # ~8天
        mock_trait.assert_called_with("conscientiousness", -0.05)


# ═══════════════════════════════════════════════════════════════
# process_daily_evolution — 每日演化主入口
# ═══════════════════════════════════════════════════════════════


class TestProcessDailyEvolution:
    @patch("core.emotion_evolution._set_last_evolution_date")
    @patch("core.emotion_evolution._rule_weekly_reflection")
    @patch("core.emotion_evolution._rule_interaction_quality")
    @patch("core.emotion_evolution._rule_habitual_closeness")
    @patch("core.emotion_evolution._rule_cold_adaptation")
    @patch("core.emotion_evolution._rule_silence_decay")
    @patch("core.emotion_evolution._check_sustained_low_mood")
    @patch("core.emotion_evolution._get_hours_since_last_interaction", return_value=10)
    @patch("core.emotion_evolution._try_claim_evolution_date", return_value=True)
    @patch("core.emotion_evolution.get_conn")
    @patch("core.emotion_evolution.datetime")
    def test_runs_all_rules(self, mock_dt, mock_conn, mock_claim, mock_hours,
                            mock_low, mock_silence, mock_cold, mock_habit,
                            mock_quality, mock_reflect, mock_set_date):
        """正常执行应触发所有规则。"""
        mock_dt.now.return_value = datetime(2026, 6, 13, 10, 0, 0)  # Friday, not Sunday
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=MagicMock(return_value=MagicMock())))
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        process_daily_evolution()
        mock_silence.assert_called_once_with(10)
        mock_cold.assert_called_once()
        mock_habit.assert_called_once()
        mock_quality.assert_called_once()
        mock_reflect.assert_not_called()  # 不是周日

    @patch("core.emotion_evolution._try_claim_evolution_date", return_value=False)
    def test_skips_if_already_done_today(self, mock_claim):
        """当天已执行过则跳过。"""
        with patch("core.emotion_evolution._rule_silence_decay") as mock_silence:
            process_daily_evolution()
            mock_silence.assert_not_called()