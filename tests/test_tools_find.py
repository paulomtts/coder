import pytest
from pygents import ContextItem
from coder.agent.tools.find import tool_find


async def _result(gen):
    values = [v async for v in gen]
    return values[0].content["content"]


@pytest.mark.asyncio
async def test_find_by_glob(tmp_path):
    (tmp_path / "foo.py").write_text("")
    (tmp_path / "bar.py").write_text("")
    (tmp_path / "baz.txt").write_text("")
    result = await _result(tool_find(pattern="*.py", path=str(tmp_path)))
    assert "foo.py" in result
    assert "bar.py" in result
    assert "baz.txt" not in result


@pytest.mark.asyncio
async def test_find_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.py").write_text("")
    result = await _result(tool_find(pattern="**/*.py", path=str(tmp_path)))
    assert "deep.py" in result


@pytest.mark.asyncio
async def test_find_no_matches(tmp_path):
    (tmp_path / "a.txt").write_text("")
    result = await _result(tool_find(pattern="*.xyz", path=str(tmp_path)))
    assert "no matches" in result.lower() or result.strip() == ""


@pytest.mark.asyncio
async def test_tool_find_yields_context_item(tmp_path):
    (tmp_path / "found.py").write_text("")
    values = [v async for v in tool_find(pattern="*.py", path=str(tmp_path))]
    assert len(values) == 1
    assert isinstance(values[0], ContextItem)
    assert values[0].content["role"] == "tool"
