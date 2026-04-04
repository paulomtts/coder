import os
import pytest
from pygents import ContextItem
from coder.agent.tools.write import tool_write


async def _result(gen):
    values = [v async for v in gen]
    return values[0].content["content"]


@pytest.mark.asyncio
async def test_write_creates_file(tmp_path):
    f = tmp_path / "new.txt"
    result = await _result(tool_write(path=str(f), content="hello world"))
    assert os.path.exists(f)
    assert f.read_text() == "hello world"
    assert "wrote" in result.lower() or "created" in result.lower()


@pytest.mark.asyncio
async def test_write_overwrites_existing(tmp_path):
    f = tmp_path / "existing.txt"
    f.write_text("old content")
    await _result(tool_write(path=str(f), content="new content"))
    assert f.read_text() == "new content"


@pytest.mark.asyncio
async def test_write_creates_parent_dirs(tmp_path):
    f = tmp_path / "a" / "b" / "c" / "deep.txt"
    await _result(tool_write(path=str(f), content="deep"))
    assert f.read_text() == "deep"


@pytest.mark.asyncio
async def test_tool_write_yields_context_item(tmp_path):
    f = tmp_path / "ctx.txt"
    values = [v async for v in tool_write(path=str(f), content="test")]
    assert len(values) == 1
    assert isinstance(values[0], ContextItem)
    assert values[0].content["role"] == "tool"
