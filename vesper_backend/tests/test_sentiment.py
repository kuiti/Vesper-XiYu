"""test_sentiment.py — api.sentiment 情感分析测试"""
import pytest
from api.sentiment import (
    analyze_sentiment, get_empathy_strategy, get_contextual_strategy,
    detect_context_keyword, FALLBACK_RESULT,
)

class TestAnalyzeSentiment:
    def test_positive_happy(self):
        r = analyze_sentiment("今天好开心啊！")
        assert r["sentiment"] == "positive"
        assert r["emotion_subtype"] == "happy_share"

    def test_positive_gratitude(self):
        r = analyze_sentiment("谢谢你，很感动")
        assert r["sentiment"] == "positive"
        assert r["intent"] == "gratitude"
        assert r["relationship_impact"] > 0

    def test_positive_proud(self):
        r = analyze_sentiment("我太棒了！成功了！")
        assert r["sentiment"] == "positive"
        assert r["emotion_subtype"] == "proud"

    def test_negative_sad(self):
        r = analyze_sentiment("我好难过，想哭")
        assert r["sentiment"] == "negative"
        assert r["emotion_subtype"] == "sad"

    def test_negative_angry(self):
        r = analyze_sentiment("气死了，太过分了！")
        assert r["sentiment"] == "negative"
        assert r["emotion_subtype"] == "angry"

    def test_negative_tired(self):
        r = analyze_sentiment("好累啊，不想动")
        assert r["sentiment"] == "negative"
        assert r["emotion_subtype"] == "tired"

    def test_neutral(self):
        r = analyze_sentiment("今天天气不错")
        assert r["sentiment"] == "neutral"
        assert r["emotion_subtype"] == "neutral"

    def test_empty_input(self):
        r = analyze_sentiment("")
        assert r["sentiment"] == "neutral"
        assert r == FALLBACK_RESULT

    def test_short_input(self):
        r = analyze_sentiment("嗯")
        assert r == FALLBACK_RESULT

    def test_playful_teasing(self):
        r = analyze_sentiment("哼，才不理你呢")
        assert r["sentiment"] == "positive"
        assert r["emotion_subtype"] == "teasing"

    def test_joking(self):
        r = analyze_sentiment("你完了，打你！")
        assert r["sentiment"] == "positive"
        assert r["intent"] == "joke"

class TestTargetDetection:
    def test_target_ai_negative(self):
        r = analyze_sentiment("你根本不懂我")
        assert r["target"] == "ai"

    def test_target_self(self):
        r = analyze_sentiment("我觉得很累")
        assert r["target"] == "self"

class TestRelationshipImpact:
    def test_impact_range(self):
        for text in ["开心", "难过", "生气", "你好"]:
            r = analyze_sentiment(text)
            assert -3.0 <= r["relationship_impact"] <= 3.0

    def test_positive_impact(self):
        r = analyze_sentiment("谢谢，好感动")
        assert r["relationship_impact"] > 0

class TestContextKeyword:
    def test_work_context(self):
        assert detect_context_keyword("老板太烦了") == "work"
    def test_love_context(self):
        assert detect_context_keyword("和男朋友吵架了") == "love"
    def test_no_context(self):
        assert detect_context_keyword("今天天气不错") is None

class TestEmpathyStrategy:
    def test_happy_returns_E(self):
        assert get_empathy_strategy("happy_share")["strategy"] == "E"
    def test_teasing_returns_F(self):
        assert get_empathy_strategy("teasing")["strategy"] == "F"
    def test_neutral_returns_none(self):
        assert get_empathy_strategy("neutral") is None
    def test_contextual_neutral(self):
        assert get_contextual_strategy("neutral", "work") is None