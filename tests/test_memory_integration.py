import pytest
from unittest.mock import AsyncMock, MagicMock

from coder.agent.memory.store import (
    MemoryEntry,
    write_entry,
    read_entry,
    list_entries,
    build_memory_index,
)
from coder.agent.memory.decay import run_decay


@pytest.mark.asyncio
async def test_full_memory_lifecycle(tmp_path):
    """Test: write semantic → read → update → build index → write episodic → decay."""

    # 1. Write a semantic entry
    write_entry(
        MemoryEntry(
            type="semantic", topic="testing", content="Uses pytest.", tags=["tools"]
        ),
        base_dir=str(tmp_path),
    )

    # 2. Read it back
    entry = read_entry("semantic", "testing", base_dir=str(tmp_path))
    assert entry.content == "Uses pytest."

    # 3. Update (overwrite)
    write_entry(
        MemoryEntry(
            type="semantic",
            topic="testing",
            content="Uses pytest with fixtures.",
            tags=["tools"],
        ),
        base_dir=str(tmp_path),
    )
    entry = read_entry("semantic", "testing", base_dir=str(tmp_path))
    assert entry.content == "Uses pytest with fixtures."

    # 4. Build index
    index = build_memory_index(base_dir=str(tmp_path))
    assert "Uses pytest with fixtures." in index

    # 5. Write episodic entries
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    for i in range(3):
        write_entry(
            MemoryEntry(
                type="episodic",
                topic=f"session-{i}",
                content=f"Worked on feature {i}.",
                created=now - timedelta(days=15 + i),
            ),
            base_dir=str(tmp_path),
        )

    # 6. Run decay
    toolkit = MagicMock()
    response = MagicMock()
    response.content = "Merged: worked on features 0-2."
    toolkit.chat = AsyncMock(return_value=response)

    await run_decay(toolkit, base_dir=str(tmp_path), now=now)

    # 7. Verify decay result
    episodic = list_entries("episodic", base_dir=str(tmp_path))
    assert len(episodic) == 1
    assert episodic[0].decay == "weekly"
    assert "Merged" in episodic[0].content
