"""test_retry.py — core.retry 工具测试"""
import pytest
from core.retry import silent_exc, retry_with_backoff

class TestSilentExc:
    def test_does_not_raise(self):
        # silent_exc 应该静默记录，不抛异常
        silent_exc("test_ctx", ValueError("test error"))
        silent_exc("test", RuntimeError("另一个错误"))

class TestRetryWithBackoff:
    def test_success_first_try(self):
        call_count = 0
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"
        assert succeed() == "ok"
        assert call_count == 1

    def test_success_after_retries(self):
        call_count = 0
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "done"
        assert fail_twice() == "done"
        assert call_count == 3

    def test_exhausted_raises(self):
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_fail():
            raise RuntimeError("always")
        with pytest.raises(RuntimeError):
            always_fail()

    def test_specific_exception_filter(self):
        call_count = 0
        @retry_with_backoff(max_retries=2, base_delay=0.01, exceptions=(ValueError,))
        def wrong_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("wrong type")
        with pytest.raises(TypeError):
            wrong_error()
        assert call_count == 1  # TypeError 不在 retry 列表中，直接抛出