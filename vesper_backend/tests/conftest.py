"""Test-level fixtures for chat and LLM testing."""

import pytest


@pytest.fixture
def thinking_parser():
    """Create a fresh ThinkingParser for each test."""
    from api.chat_parser import ThinkingParser
    return ThinkingParser()


@pytest.fixture
def sample_messages():
    """Sample chat messages for testing."""
    return [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！今天过得怎么样？"},
        {"role": "user", "content": "挺好的，今天去公园散步了"},
        {"role": "assistant", "content": "听起来不错，天气好吗？"},
    ]
