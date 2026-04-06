# tests/test_memory_commands.py
import pytest
from unittest.mock import MagicMock
from pygents import ContextItem, ContextPool

from coder.agent.memory.store import MemoryEntry, write_entry, read_entry


@pytest.mark.asyncio
async def test_handle_forget(tmp_path):
    write_entry(
        MemoryEntry(type="semantic", topic="old-fact", content="Old.", tags=[]),
        base_dir=str(tmp_path),
    )

    session = MagicMock()
    session.config = MagicMock()
    session.config.memory_dir = str(tmp_path)
    session.pool = ContextPool()
    await session.pool.add(
        ContextItem(id="semantic-memory", description="mem", content="Old.")
    )

    from coder.cli.repl import handle_input

    result = await handle_input(session, "/forget old-fact")
    assert result is None
    assert read_entry("semantic", "old-fact", base_dir=str(tmp_path)) is None


@pytest.mark.asyncio
async def test_handle_memories(tmp_path):
    write_entry(
        MemoryEntry(type="semantic", topic="prefs", content="Likes Python.", tags=[]),
        base_dir=str(tmp_path),
    )

    session = MagicMock()
    session.config = MagicMock()
    session.config.memory_dir = str(tmp_path)

    from coder.cli.repl import handle_input

    result = await handle_input(session, "/memories")
    assert result is None


@pytest.mark.asyncio
async def test_handle_remember(tmp_path):
    session = MagicMock()
    session.config = MagicMock()
    session.config.memory_dir = str(tmp_path)
    session.config.cwd = str(tmp_path)

    from coder.cli.repl import handle_input

    result = await handle_input(session, "/remember I prefer pytest over unittest")
    assert result is not None
    assert "remember" in result.lower() or "pytest" in result.lower()


@pytest.mark.asyncio
async def test_handle_recall(tmp_path):
    write_entry(
        MemoryEntry(
            type="episodic",
            topic="2026-04-01T10-00-00",
            content="Worked on auth module refactor.",
            tags=[],
        ),
        base_dir=str(tmp_path),
    )

    session = MagicMock()
    session.config = MagicMock()
    session.config.memory_dir = str(tmp_path)

    from coder.cli.repl import handle_input

    result = await handle_input(session, "/recall auth")
    assert result is None
