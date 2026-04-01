import asyncio
import pytest
from pygents import ContextPool, ContextQueue
from coder.agent_loop import create_agent, register_all_tools

@pytest.mark.asyncio
async def test_register_all_tools():
    register_all_tools()
    from pygents.registry import ToolRegistry
    assert ToolRegistry.get("tool_read") is not None
    assert ToolRegistry.get("tool_write") is not None
    assert ToolRegistry.get("tool_edit") is not None
    assert ToolRegistry.get("tool_bash") is not None
    assert ToolRegistry.get("tool_grep") is not None
    assert ToolRegistry.get("tool_find") is not None
    assert ToolRegistry.get("tool_ls") is not None

@pytest.mark.asyncio
async def test_create_agent():
    register_all_tools()
    pool = ContextPool()
    cq = ContextQueue(limit=10)
    agent = create_agent(pool=pool, cq=cq)
    assert agent.name == "coder"
    assert len(agent.tools) > 0
