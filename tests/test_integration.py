# tests/test_integration.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from coder.agent.session import Session


@pytest.mark.asyncio
async def test_session_start(tmp_path):
    session = Session()
    with patch.dict(
        "os.environ", {"LLM_MODEL": "test-model", "LLM_API_KEY": "test-key"}
    ):
        await session.start(cwd=str(tmp_path))
    assert session.agent is not None
    assert session.agent.name == "coder"
    assert session.pool.get("base-prompt") is not None
    assert session.toolkit is not None


@pytest.mark.asyncio
async def test_session_with_project_context(tmp_path):
    (tmp_path / "AGENTS.md").write_text("Be helpful and concise.")
    session = Session()
    with patch.dict(
        "os.environ", {"LLM_MODEL": "test-model", "LLM_API_KEY": "test-key"}
    ):
        await session.start(cwd=str(tmp_path))
    ctx = session.pool.get("project-context")
    assert "Be helpful" in str(ctx.content)


@pytest.mark.asyncio
async def test_session_role_switching(tmp_path):
    session = Session()
    with patch.dict(
        "os.environ", {"LLM_MODEL": "test-model", "LLM_API_KEY": "test-key"}
    ):
        await session.start(cwd=str(tmp_path))
    session.toolkit.chat = AsyncMock(return_value=MagicMock(content="Branch summary"))
    await session.switch_role("scout")
    role = session.pool.get("active-role")
    assert (
        "scout" in str(role.content).lower()
        or "investigate" in str(role.content).lower()
    )
    allowed_tools_item = session.pool.get("allowed-tools")
    assert allowed_tools_item is not None
    assert "tool_write" not in allowed_tools_item.content
