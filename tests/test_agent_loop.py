# tests/test_agent_loop.py
import asyncio
import pytest
from unittest.mock import MagicMock
from pygents import ContextPool, ContextQueue

from coder.agent.loop import create_agent


@pytest.mark.asyncio
async def test_create_agent_has_all_tools():
    """Agent should have file/shell tools + llm_decide + llm_respond."""
    session = MagicMock()
    session.toolkit = MagicMock()
    session.steering_queue = asyncio.Queue()
    session.config = MagicMock()
    session.config.compaction_threshold = 0.8
    session.config.keep_recent_tokens = 20000

    pool = ContextPool()
    cq = ContextQueue(limit=10)
    agent = create_agent(pool=pool, cq=cq)

    tool_names = {t.metadata.name for t in agent.tools}
    assert "tool_read" in tool_names
    assert "tool_write" in tool_names
    assert "tool_edit" in tool_names
    assert "tool_bash" in tool_names
    assert "tool_grep" in tool_names
    assert "tool_find" in tool_names
    assert "tool_ls" in tool_names
    assert "llm_decide" in tool_names
    assert "llm_respond" in tool_names


@pytest.mark.asyncio
async def test_create_agent_name():
    session = MagicMock()
    session.toolkit = MagicMock()
    session.steering_queue = asyncio.Queue()
    session.config = MagicMock()
    session.config.compaction_threshold = 0.8
    session.config.keep_recent_tokens = 20000

    pool = ContextPool()
    cq = ContextQueue(limit=10)
    agent = create_agent(pool=pool, cq=cq)
    assert agent.name == "coder"
