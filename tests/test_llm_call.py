import pytest
from pygents import ContextItem, ContextPool, ContextQueue
from coder.llm_call import build_system_prompt, build_messages

def test_build_system_prompt_basic():
    pool = ContextPool()
    pool._items["base-prompt"] = ContextItem(id="base-prompt", description="Base system prompt", content="You are a coding assistant.\n\nGuidelines:\n{guidelines}")
    prompt = build_system_prompt(pool, allowed_tools=None, tools_list="- read\n- bash")
    assert "coding assistant" in prompt
    assert "read" in prompt

def test_build_system_prompt_with_role():
    pool = ContextPool()
    pool._items["base-prompt"] = ContextItem(id="base-prompt", description="Base", content="Base prompt.\n\nGuidelines:\n{guidelines}")
    pool._items["active-role"] = ContextItem(id="active-role", description="Active role", content="You are a scout.")
    prompt = build_system_prompt(pool, allowed_tools=None, tools_list="- read")
    assert "scout" in prompt

def test_build_messages():
    cq = ContextQueue(limit=10)
    cq._items.append(ContextItem(content={"role": "user", "content": "hello"}))
    cq._items.append(ContextItem(content={"role": "assistant", "content": "hi there"}))
    messages = build_messages(cq)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

def test_build_messages_with_compaction_summary():
    cq = ContextQueue(limit=10)
    cq._items.append(ContextItem(content={"role": "user", "content": "hello"}))
    messages = build_messages(cq, compaction_summary="Previous work summary here.")
    assert len(messages) == 2
    assert "Previous work" in messages[0]["content"]
    assert messages[0]["role"] == "system"
