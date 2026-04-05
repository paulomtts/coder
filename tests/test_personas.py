import pytest
from coder.agent.personas.definitions import PERSONAS, get_persona, get_allowed_tools


def test_all_personas_exist():
    assert "scout" in PERSONAS
    assert "planner" in PERSONAS
    assert "worker" in PERSONAS
    assert "reviewer" in PERSONAS


def test_get_persona():
    persona = get_persona("scout")
    assert persona.name == "scout"
    assert persona.system_prompt
    assert (
        "scout" in persona.system_prompt.lower()
        or "investigate" in persona.system_prompt.lower()
    )


def test_get_persona_not_found():
    with pytest.raises(KeyError):
        get_persona("nonexistent")


def test_scout_tools():
    tools = get_allowed_tools("scout")
    assert "tool_read" in tools
    assert "tool_bash" in tools
    assert "tool_grep" in tools
    assert "tool_find" in tools
    assert "tool_ls" in tools
    assert "tool_write" not in tools
    assert "tool_edit" not in tools


def test_worker_tools():
    tools = get_allowed_tools("worker")
    assert "tool_read" in tools
    assert "tool_write" in tools
    assert "tool_edit" in tools
    assert "tool_bash" in tools


def test_reviewer_no_write_tools():
    tools = get_allowed_tools("reviewer")
    assert "tool_write" not in tools
    assert "tool_edit" not in tools


@pytest.mark.asyncio
async def test_switch_role_stores_allowed_tools_on_session():
    """switch_role should store allowed_tools on the session for llm_decide to read."""
    from unittest.mock import AsyncMock, MagicMock
    from coder.agent.session import Session
    from pygents import ContextPool, ContextQueue

    session = Session()
    session.toolkit = AsyncMock()
    session.toolkit.chat = AsyncMock(return_value=MagicMock(content="Branch summary"))
    session.cq = ContextQueue(limit=10)
    session.pool = ContextPool()

    await session.switch_role("scout")

    assert session._allowed_tools is not None
    assert "tool_read" in session._allowed_tools
    assert "tool_write" not in session._allowed_tools  # scout can't write
