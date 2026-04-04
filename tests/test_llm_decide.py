# tests/test_llm_decide.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from pygents import ContextItem, ContextPool, ContextQueue, Turn
from pygents.registry import ToolRegistry

from coder.agent.llm.decide import llm_decide, AgentResponse, ToolCallRequest


def _register_tools():
    """Register the tools referenced by llm_decide (file/shell tools + llm_decide + llm_respond)."""
    from coder.agent.tools import ALL_TOOLS
    from coder.agent.llm.respond import llm_respond

    for t in ALL_TOOLS:
        if ToolRegistry._registry.get(t.__name__) is None:
            ToolRegistry.register(t)
    if ToolRegistry._registry.get(llm_decide.__name__) is None:
        ToolRegistry.register(llm_decide)
    if ToolRegistry._registry.get(llm_respond.__name__) is None:
        ToolRegistry.register(llm_respond)


@pytest.fixture
def pool():
    pool = ContextPool()
    pool._items["base-prompt"] = ContextItem(
        id="base-prompt",
        description="Base system prompt",
        content="You are a coding assistant.\n\nAvailable tools:\n{tools_list}\n\nGuidelines:\n{guidelines}",
    )
    return pool


@pytest.fixture
def cq():
    cq = ContextQueue(limit=10)
    cq._items.append(ContextItem(content={"role": "user", "content": "Read foo.py"}))
    return cq


@pytest.mark.asyncio
async def test_llm_decide_yields_tool_turns(pool, cq):
    """When LLM returns tool calls, llm_decide yields ContextItem + Turn per tool + Turn(llm_decide)."""
    _register_tools()

    mock_toolkit = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = AgentResponse(
        text=None,
        tool_calls=[ToolCallRequest(name="tool_read", arguments={"path": "foo.py"})],
    )
    mock_toolkit.asend = AsyncMock(return_value=mock_response)

    yielded = []
    async for value in llm_decide(cq=cq, pool=pool, toolkit=mock_toolkit):
        yielded.append(value)

    # First yield: ContextItem (assistant message)
    assert isinstance(yielded[0], ContextItem)
    assert yielded[0].content["role"] == "assistant"

    # Second yield: Turn for tool_read
    assert isinstance(yielded[1], Turn)
    assert yielded[1].tool.metadata.name == "tool_read"

    # Third yield: Turn for llm_decide (self-enqueue)
    assert isinstance(yielded[2], Turn)
    assert yielded[2].tool.metadata.name == "llm_decide"


@pytest.mark.asyncio
async def test_llm_decide_yields_respond_turn_when_no_tools(pool, cq):
    """When LLM returns text only, llm_decide yields ContextItem + Turn(llm_respond)."""
    _register_tools()

    mock_toolkit = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = AgentResponse(
        text="The file contains a greeting function.",
        tool_calls=None,
    )
    mock_toolkit.asend = AsyncMock(return_value=mock_response)

    yielded = []
    async for value in llm_decide(cq=cq, pool=pool, toolkit=mock_toolkit):
        yielded.append(value)

    assert isinstance(yielded[0], ContextItem)
    assert yielded[0].content["role"] == "assistant"
    assert isinstance(yielded[1], Turn)
    assert yielded[1].tool.metadata.name == "llm_respond"


@pytest.mark.asyncio
async def test_llm_decide_yields_multiple_tool_turns(pool, cq):
    """When LLM returns multiple tool calls, llm_decide yields one Turn per tool + self-enqueue."""
    _register_tools()

    mock_toolkit = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = AgentResponse(
        text=None,
        tool_calls=[
            ToolCallRequest(name="tool_read", arguments={"path": "a.py"}),
            ToolCallRequest(name="tool_read", arguments={"path": "b.py"}),
            ToolCallRequest(name="tool_grep", arguments={"pattern": "def main"}),
        ],
    )
    mock_toolkit.asend = AsyncMock(return_value=mock_response)

    yielded = []
    async for value in llm_decide(cq=cq, pool=pool, toolkit=mock_toolkit):
        yielded.append(value)

    # 1 ContextItem + 3 tool Turns + 1 self-enqueue Turn = 5
    assert len(yielded) == 5
    assert isinstance(yielded[0], ContextItem)
    assert all(isinstance(y, Turn) for y in yielded[1:])
    assert yielded[-1].tool.metadata.name == "llm_decide"
