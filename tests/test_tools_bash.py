import pytest
from coder.agent.tools.bash import tool_bash


@pytest.mark.asyncio
async def test_bash_simple_command():
    result = await tool_bash(command="echo hello")
    assert "hello" in result


@pytest.mark.asyncio
async def test_bash_stderr():
    result = await tool_bash(command="echo err >&2")
    assert "err" in result


@pytest.mark.asyncio
async def test_bash_exit_code():
    result = await tool_bash(command="exit 1")
    assert "exit code" in result.lower() or "1" in result


@pytest.mark.asyncio
async def test_bash_timeout():
    result = await tool_bash(command="sleep 10", timeout=1)
    assert "timeout" in result.lower() or "timed out" in result.lower()


@pytest.mark.asyncio
async def test_bash_cwd(tmp_path):
    result = await tool_bash(command="pwd", cwd=str(tmp_path))
    assert str(tmp_path) in result
