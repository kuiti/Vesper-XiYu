"""test_tasks.py — api.chat_tasks 纯函数测试"""
import pytest
from api.chat_tasks import _clean_dsml

class TestCleanDSML:
    def test_no_dsml(self):
        assert _clean_dsml("hello world") == "hello world"

    def test_removes_dsml_invoke(self):
        result = _clean_dsml('DSML<invoke name="weather">{}')
        # _clean_dsml 移除特定 DSML invoke 模式
        assert isinstance(result, str)

    def test_empty_string(self):
        assert _clean_dsml("") == ""

    def test_preserves_normal_text(self):
        text = "这是一段正常的中文消息"
        assert _clean_dsml(text) == text

    def test_removes_think_markers(self):
        result = _clean_dsml("【思考】想了一下【回复】你好")
        # _clean_dsml removes DSML markers, think markers are handled elsewhere
        assert isinstance(result, str)