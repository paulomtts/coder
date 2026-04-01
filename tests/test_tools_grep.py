import pytest
from coder.agent.tools.grep import tool_grep


@pytest.mark.asyncio
async def test_grep_finds_pattern(tmp_path):
    (tmp_path / "a.py").write_text("def hello():\n    pass\n")
    (tmp_path / "b.py").write_text("def world():\n    pass\n")
    result = await tool_grep(pattern="hello", path=str(tmp_path))
    assert "a.py" in result
    assert "hello" in result


@pytest.mark.asyncio
async def test_grep_respects_glob_filter(tmp_path):
    (tmp_path / "code.py").write_text("match here\n")
    (tmp_path / "notes.txt").write_text("match here too\n")
    result = await tool_grep(pattern="match", path=str(tmp_path), glob="*.py")
    assert "code.py" in result
    assert "notes.txt" not in result


@pytest.mark.asyncio
async def test_grep_case_insensitive(tmp_path):
    (tmp_path / "f.txt").write_text("Hello World\n")
    result = await tool_grep(pattern="hello", path=str(tmp_path), ignore_case=True)
    assert "Hello" in result


@pytest.mark.asyncio
async def test_grep_no_matches(tmp_path):
    (tmp_path / "f.txt").write_text("nothing here\n")
    result = await tool_grep(pattern="zzzzz", path=str(tmp_path))
    assert "no matches" in result.lower() or result.strip() == ""
