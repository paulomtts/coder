import os
import pytest
from coder.tools.read import tool_read

@pytest.mark.asyncio
async def test_read_text_file(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("line1\nline2\nline3\n")
    result = await tool_read(path=str(f))
    assert "line1" in result
    assert "line2" in result
    assert "line3" in result

@pytest.mark.asyncio
async def test_read_with_offset_and_limit(tmp_path):
    f = tmp_path / "lines.txt"
    f.write_text("\n".join(f"line{i}" for i in range(1, 11)))
    result = await tool_read(path=str(f), offset=3, limit=2)
    assert "line3" in result
    assert "line4" in result
    assert "line1" not in result
    assert "line5" not in result

@pytest.mark.asyncio
async def test_read_nonexistent_file():
    result = await tool_read(path="/tmp/nonexistent_file_xyz.txt")
    assert "error" in result.lower() or "not found" in result.lower()

@pytest.mark.asyncio
async def test_read_truncates_large_output(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * (300 * 1024))
    result = await tool_read(path=str(f))
    assert len(result) <= 260 * 1024
    assert "truncated" in result.lower()

@pytest.mark.asyncio
async def test_read_truncates_many_lines(tmp_path):
    f = tmp_path / "many_lines.txt"
    f.write_text("\n".join(f"line{i}" for i in range(3000)))
    result = await tool_read(path=str(f))
    assert "truncated" in result.lower()
