import pytest
from coder.agent.tools.find import tool_find


@pytest.mark.asyncio
async def test_find_by_glob(tmp_path):
    (tmp_path / "foo.py").write_text("")
    (tmp_path / "bar.py").write_text("")
    (tmp_path / "baz.txt").write_text("")
    result = await tool_find(pattern="*.py", path=str(tmp_path))
    assert "foo.py" in result
    assert "bar.py" in result
    assert "baz.txt" not in result


@pytest.mark.asyncio
async def test_find_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.py").write_text("")
    result = await tool_find(pattern="**/*.py", path=str(tmp_path))
    assert "deep.py" in result


@pytest.mark.asyncio
async def test_find_no_matches(tmp_path):
    (tmp_path / "a.txt").write_text("")
    result = await tool_find(pattern="*.xyz", path=str(tmp_path))
    assert "no matches" in result.lower() or result.strip() == ""
