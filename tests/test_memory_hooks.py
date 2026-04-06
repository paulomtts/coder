# tests/test_memory_hooks.py
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pygents import Agent, ContextItem, ContextPool, ContextQueue, Turn

from coder.agent.hooks import extract_memories
from coder.agent.memory.store import read_entry, list_entries


@pytest.mark.asyncio
async def test_extract_memories_writes_facts(tmp_path):
    agent = MagicMock(spec=Agent)
    agent.context_pool = ContextPool()
    await agent.context_pool.add(
        ContextItem(id="semantic-memory", description="Semantic memory", content="")
    )

    turn = MagicMock(spec=Turn)
    turn.tool = MagicMock()
    turn.tool.metadata = MagicMock()
    turn.tool.metadata.name = "llm_respond"
    turn.output = [
        ContextItem(content={"role": "assistant", "content": "Sure, I'll use spaces."})
    ]

    # Mock the context queue to have the user message
    agent.context_queue = ContextQueue(limit=100)
    await agent.context_queue.append(
        ContextItem(content={"role": "user", "content": "always use spaces not tabs"})
    )

    mock_toolkit = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps(
        [{"topic": "user-preferences", "content": "Prefers spaces over tabs."}]
    )
    mock_toolkit.chat = AsyncMock(return_value=mock_response)

    with patch("coder.agent.hooks.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.toolkit = mock_toolkit
        mock_session.config = MagicMock()
        mock_session.config.memory_dir = str(tmp_path)
        mock_get_session.return_value = mock_session

        await extract_memories(agent, turn)

    entry = read_entry("semantic", "user-preferences", base_dir=str(tmp_path))
    assert entry is not None
    assert entry.content == "Prefers spaces over tabs."


@pytest.mark.asyncio
async def test_extract_memories_skips_non_respond_tools(tmp_path):
    agent = MagicMock(spec=Agent)
    turn = MagicMock(spec=Turn)
    turn.tool = MagicMock()
    turn.tool.metadata = MagicMock()
    turn.tool.metadata.name = "tool_read"

    with patch("coder.agent.hooks.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.config = MagicMock()
        mock_session.config.memory_dir = str(tmp_path)
        mock_get_session.return_value = mock_session

        await extract_memories(agent, turn)

    assert list_entries("semantic", base_dir=str(tmp_path)) == []
