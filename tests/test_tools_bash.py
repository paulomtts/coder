import pytest
from pygents import ContextItem
from coder.agent.tools.bash import tool_bash


async def _result(gen):
    values = [v async for v in gen]
    return values[0].content["content"]


@pytest.mark.asyncio
async def test_bash_simple_command():
    result = await _result(tool_bash(command="echo hello"))
    assert "hello" in result


@pytest.mark.asyncio
async def test_bash_stderr():
    result = await _result(tool_bash(command="echo err >&2"))
    assert "err" in result


@pytest.mark.asyncio
async def test_bash_exit_code():
    result = await _result(tool_bash(command="exit 1"))
    assert "exit code" in result.lower() or "1" in result


@pytest.mark.asyncio
async def test_bash_timeout():
    result = await _result(tool_bash(command="sleep 10", timeout=1))
    assert "timeout" in result.lower() or "timed out" in result.lower()


@pytest.mark.asyncio
async def test_bash_cwd(tmp_path):
    result = await _result(tool_bash(command="pwd", cwd=str(tmp_path)))
    assert str(tmp_path) in result


@pytest.mark.asyncio
async def test_tool_bash_yields_context_item():
    values = [v async for v in tool_bash(command="echo hi")]
    assert len(values) == 1
    assert isinstance(values[0], ContextItem)
    assert values[0].content["role"] == "tool"
