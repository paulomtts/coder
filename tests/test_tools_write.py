import os
import pytest
from coder.agent.tools.write import tool_write

@pytest.mark.asyncio
async def test_write_creates_file(tmp_path):
    f = tmp_path / "new.txt"
    result = await tool_write(path=str(f), content="hello world")
    assert os.path.exists(f)
    assert f.read_text() == "hello world"
    assert "wrote" in result.lower() or "created" in result.lower()

@pytest.mark.asyncio
async def test_write_overwrites_existing(tmp_path):
    f = tmp_path / "existing.txt"
    f.write_text("old content")
    await tool_write(path=str(f), content="new content")
    assert f.read_text() == "new content"

@pytest.mark.asyncio
async def test_write_creates_parent_dirs(tmp_path):
    f = tmp_path / "a" / "b" / "c" / "deep.txt"
    await tool_write(path=str(f), content="deep")
    assert f.read_text() == "deep"
