import pytest
from pygents import ContextItem
from coder.agent.tools.edit import tool_edit


async def _result(gen):
    values = [v async for v in gen]
    return values[0].content["content"]


@pytest.mark.asyncio
async def test_edit_single_replacement(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("def hello():\n    return 'world'\n")
    result = await _result(
        tool_edit(
            path=str(f),
            edits=[{"old_text": "return 'world'", "new_text": "return 'universe'"}],
        )
    )
    assert f.read_text() == "def hello():\n    return 'universe'\n"
    assert "applied" in result.lower()


@pytest.mark.asyncio
async def test_edit_multiple_replacements(tmp_path):
    f = tmp_path / "multi.py"
    f.write_text("aaa\nbbb\nccc\n")
    await _result(
        tool_edit(
            path=str(f),
            edits=[
                {"old_text": "aaa", "new_text": "AAA"},
                {"old_text": "ccc", "new_text": "CCC"},
            ],
        )
    )
    assert f.read_text() == "AAA\nbbb\nCCC\n"


@pytest.mark.asyncio
async def test_edit_old_text_not_found(tmp_path):
    f = tmp_path / "miss.py"
    f.write_text("hello world\n")
    result = await _result(
        tool_edit(path=str(f), edits=[{"old_text": "goodbye", "new_text": "hi"}])
    )
    assert "not found" in result.lower() or "error" in result.lower()
    assert f.read_text() == "hello world\n"


@pytest.mark.asyncio
async def test_edit_old_text_not_unique(tmp_path):
    f = tmp_path / "dup.py"
    f.write_text("foo\nfoo\n")
    result = await _result(
        tool_edit(path=str(f), edits=[{"old_text": "foo", "new_text": "bar"}])
    )
    assert (
        "unique" in result.lower()
        or "multiple" in result.lower()
        or "error" in result.lower()
    )
    assert f.read_text() == "foo\nfoo\n"


@pytest.mark.asyncio
async def test_edit_nonexistent_file():
    result = await _result(
        tool_edit(
            path="/tmp/nonexistent_xyz.py", edits=[{"old_text": "a", "new_text": "b"}]
        )
    )
    assert "error" in result.lower()


@pytest.mark.asyncio
async def test_tool_edit_yields_context_item(tmp_path):
    f = tmp_path / "ctx.py"
    f.write_text("old\n")
    values = [
        v
        async for v in tool_edit(
            path=str(f), edits=[{"old_text": "old", "new_text": "new"}]
        )
    ]
    assert len(values) == 1
    assert isinstance(values[0], ContextItem)
    assert values[0].content["role"] == "tool"
