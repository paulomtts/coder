import pytest
from pygents import ContextItem
from coder.agent.compaction.summarizer import estimate_tokens, should_compact, split_messages
from coder.agent.compaction.prompts import (
    SUMMARIZATION_PROMPT, SUMMARIZATION_SYSTEM_PROMPT, UPDATE_SUMMARIZATION_PROMPT,
)

def test_estimate_tokens():
    items = [ContextItem(content={"role": "user", "content": "hello world"})]
    tokens = estimate_tokens(items)
    assert tokens > 0
    assert tokens == len(str({"role": "user", "content": "hello world"})) // 4

def test_should_compact_under_threshold():
    items = [ContextItem(content={"role": "user", "content": "short"})]
    assert not should_compact(items, threshold=0.8, max_context_tokens=100000)

def test_should_compact_over_threshold():
    big_content = "x" * 400000
    items = [ContextItem(content={"role": "user", "content": big_content})]
    assert should_compact(items, threshold=0.8, max_context_tokens=50000)

def test_split_messages():
    items = [ContextItem(content={"role": "user", "content": f"msg{i}"}) for i in range(10)]
    old, recent = split_messages(items, keep_recent_tokens=50)
    assert len(old) + len(recent) == 10
    assert len(recent) > 0
    assert len(old) > 0

def test_summarization_prompts_exist():
    assert "Goal" in SUMMARIZATION_PROMPT
    assert "Progress" in SUMMARIZATION_PROMPT
    assert "context summarization" in SUMMARIZATION_SYSTEM_PROMPT.lower()
    assert "PRESERVE" in UPDATE_SUMMARIZATION_PROMPT
