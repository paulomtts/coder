import os
import pytest
from coder.tools.ls import tool_ls

@pytest.mark.asyncio
async def test_ls_lists_files(tmp_path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "b.py").write_text("")
    result = await tool_ls(path=str(tmp_path))
    assert "a.txt" in result
    assert "b.py" in result

@pytest.mark.asyncio
async def test_ls_marks_directories(tmp_path):
    (tmp_path / "subdir").mkdir()
    (tmp_path / "file.txt").write_text("")
    result = await tool_ls(path=str(tmp_path))
    assert "subdir/" in result
    assert "file.txt" in result

@pytest.mark.asyncio
async def test_ls_sorted_alphabetically(tmp_path):
    (tmp_path / "zebra.txt").write_text("")
    (tmp_path / "alpha.txt").write_text("")
    result = await tool_ls(path=str(tmp_path))
    alpha_pos = result.index("alpha.txt")
    zebra_pos = result.index("zebra.txt")
    assert alpha_pos < zebra_pos

@pytest.mark.asyncio
async def test_ls_includes_dotfiles(tmp_path):
    (tmp_path / ".hidden").write_text("")
    (tmp_path / "visible.txt").write_text("")
    result = await tool_ls(path=str(tmp_path))
    assert ".hidden" in result

@pytest.mark.asyncio
async def test_ls_nonexistent_path():
    result = await tool_ls(path="/tmp/nonexistent_dir_xyz")
    assert "error" in result.lower()
