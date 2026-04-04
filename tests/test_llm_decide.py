# tests/test_llm_decide.py
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from pygents import ContextItem, ContextPool, ContextQueue, Turn

from coder.agent.loop import create_agent
from coder.agent.llm.decide import AgentResponse, ToolCallRequest
from coder.agent.tools.llm_decide import llm_decide


@pytest.fixture
def session():
    s = MagicMock()
    s.toolkit = AsyncMock()
    s.steering_queue = asyncio.Queue()
    s.config = MagicMock()
    s.config.compaction_threshold = 0.8
    s.config.keep_recent_tokens = 20000
    return s


@pytest.fixture
def pool(session):
    pool = ContextPool()
    pool._items["base-prompt"] = ContextItem(
        id="base-prompt",
        description="Base system prompt",
        content="You are a coding assistant.\n\nAvailable tools:\n{tools_list}\n\nGuidelines:\n{guidelines}",
    )
    pool._items["session"] = ContextItem(
        id="session",
        description="Session reference",
        content=session,
    )
    return pool


@pytest.fixture
def cq():
    cq = ContextQueue(limit=10)
    cq._items.append(ContextItem(content={"role": "user", "content": "Read foo.py"}))
    return cq


@pytest.fixture
def agent(pool, cq):
    return create_agent(pool=pool, cq=cq)


@pytest.mark.asyncio
async def test_llm_decide_yields_tool_turns(agent, session, pool, cq):
    """When LLM returns tool calls, llm_decide yields ContextItem + Turn per tool + Turn(llm_decide)."""
    mock_response = MagicMock()
    mock_response.content = AgentResponse(
        text=None,
        tool_calls=[ToolCallRequest(name="read", arguments={"path": "foo.py"})],
    )
    session.toolkit.asend = AsyncMock(return_value=mock_response)

    yielded = []
    async for value in llm_decide(cq=cq, pool=pool):
        yielded.append(value)

    # First yield: ContextItem (assistant message)
    assert isinstance(yielded[0], ContextItem)
    assert yielded[0].content["role"] == "assistant"

    # Second yield: Turn for tool_read (re-prefixed!)
    assert isinstance(yielded[1], Turn)
    assert yielded[1].tool.metadata.name == "tool_read"

    # Third yield: Turn for llm_decide (self-enqueue)
    assert isinstance(yielded[2], Turn)
    assert yielded[2].tool.metadata.name == "llm_decide"


@pytest.mark.asyncio
async def test_llm_decide_yields_respond_turn_when_no_tools(agent, session, pool, cq):
    """When LLM returns text only, llm_decide yields ContextItem + Turn(llm_respond)."""
    mock_response = MagicMock()
    mock_response.content = AgentResponse(
        text="The file contains a greeting function.",
        tool_calls=None,
    )
    session.toolkit.asend = AsyncMock(return_value=mock_response)

    yielded = []
    async for value in llm_decide(cq=cq, pool=pool):
        yielded.append(value)

    assert isinstance(yielded[0], ContextItem)
    assert yielded[0].content["role"] == "assistant"
    assert isinstance(yielded[1], Turn)
    assert yielded[1].tool.metadata.name == "llm_respond"


@pytest.mark.asyncio
async def test_llm_decide_yields_multiple_tool_turns(agent, session, pool, cq):
    """When LLM returns multiple tool calls, llm_decide yields one Turn per tool + self-enqueue."""
    mock_response = MagicMock()
    mock_response.content = AgentResponse(
        text=None,
        tool_calls=[
            ToolCallRequest(name="read", arguments={"path": "a.py"}),
            ToolCallRequest(name="read", arguments={"path": "b.py"}),
            ToolCallRequest(name="grep", arguments={"pattern": "def main"}),
        ],
    )
    session.toolkit.asend = AsyncMock(return_value=mock_response)

    yielded = []
    async for value in llm_decide(cq=cq, pool=pool):
        yielded.append(value)

    # 1 ContextItem + 3 tool Turns + 1 self-enqueue Turn = 5
    assert len(yielded) == 5
    assert isinstance(yielded[0], ContextItem)
    assert all(isinstance(y, Turn) for y in yielded[1:])
    assert yielded[-1].tool.metadata.name == "llm_decide"
