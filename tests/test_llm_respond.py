# tests/test_llm_respond.py
import asyncio
import pytest
from unittest.mock import MagicMock
from pygents import ContextItem, ContextPool, ContextQueue

from coder.agent.loop import create_agent


@pytest.fixture
def session():
    s = MagicMock()
    s.toolkit = MagicMock()
    s.steering_queue = asyncio.Queue()
    s.config = MagicMock()
    s.config.compaction_threshold = 0.8
    s.config.keep_recent_tokens = 20000
    return s


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
    cq._items.append(ContextItem(content={"role": "user", "content": "Hello"}))
    return cq


async def _fake_stream(*args, **kwargs):
    """Simulate toolkit.stream() yielding chunks."""
    chunks = ["Hello", ", ", "world", "!"]
    for text in chunks:
        chunk = MagicMock()
        chunk.content = text
        yield chunk


@pytest.mark.asyncio
async def test_llm_respond_yields_chunks_then_context_item(session, pool, cq):
    """llm_respond yields text chunks then a final ContextItem."""
    session.toolkit.stream = _fake_stream
    create_agent(session=session, pool=pool, cq=cq)

    llm_respond = session._llm_respond
    yielded = []
    async for value in llm_respond(cq=cq, pool=pool):
        yielded.append(value)

    # First 4 yields: text chunks
    assert yielded[0] == "Hello"
    assert yielded[1] == ", "
    assert yielded[2] == "world"
    assert yielded[3] == "!"

    # Last yield: ContextItem with full text
    assert isinstance(yielded[4], ContextItem)
    assert yielded[4].content["role"] == "assistant"
    assert yielded[4].content["content"] == "Hello, world!"
