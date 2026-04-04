import pytest
from pygents import ContextItem
from coder.agent.tools.ls import tool_ls


async def _result(gen):
    values = [v async for v in gen]
    return values[0].content["content"]


@pytest.mark.asyncio
async def test_ls_lists_files(tmp_path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "b.py").write_text("")
    result = await _result(tool_ls(path=str(tmp_path)))
    assert "a.txt" in result
    assert "b.py" in result


@pytest.mark.asyncio
async def test_ls_marks_directories(tmp_path):
    (tmp_path / "subdir").mkdir()
    (tmp_path / "file.txt").write_text("")
    result = await _result(tool_ls(path=str(tmp_path)))
    assert "subdir/" in result
    assert "file.txt" in result


@pytest.mark.asyncio
async def test_ls_sorted_alphabetically(tmp_path):
    (tmp_path / "zebra.txt").write_text("")
    (tmp_path / "alpha.txt").write_text("")
    result = await _result(tool_ls(path=str(tmp_path)))
    alpha_pos = result.index("alpha.txt")
    zebra_pos = result.index("zebra.txt")
    assert alpha_pos < zebra_pos


@pytest.mark.asyncio
async def test_ls_includes_dotfiles(tmp_path):
    (tmp_path / ".hidden").write_text("")
    (tmp_path / "visible.txt").write_text("")
    result = await _result(tool_ls(path=str(tmp_path)))
    assert ".hidden" in result


@pytest.mark.asyncio
async def test_ls_nonexistent_path():
    result = await _result(tool_ls(path="/tmp/nonexistent_dir_xyz"))
    assert "error" in result.lower()


@pytest.mark.asyncio
async def test_tool_ls_yields_context_item(tmp_path):
    (tmp_path / "item.txt").write_text("")
    values = [v async for v in tool_ls(path=str(tmp_path))]
    assert len(values) == 1
    assert isinstance(values[0], ContextItem)
    assert values[0].content["role"] == "tool"
