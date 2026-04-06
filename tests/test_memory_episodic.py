# tests/test_memory_episodic.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pygents import ContextItem, ContextPool, ContextQueue

from coder.agent.memory.store import list_entries


@pytest.mark.asyncio
async def test_compact_saves_episodic_entry(tmp_path):
    from coder.agent.tools.compact import compact

    session = MagicMock()
    session.toolkit = MagicMock()
    session.config = MagicMock()
    session.config.keep_recent_tokens = 20000
    session.config.memory_dir = str(tmp_path)

    pool = ContextPool()
    cq = ContextQueue(limit=100)
    # Add enough items for compaction to have old messages
    for i in range(10):
        await cq.append(
            ContextItem(
                content={"role": "user", "content": f"message {i} " + "x" * 500}
            )
        )

    summary_text = "Summary of the conversation."

    with patch("coder.agent.tools.compact.get_session", return_value=session):
        with patch(
            "coder.agent.tools.compact.run_compaction", new_callable=AsyncMock
        ) as mock_compact:
            mock_compact.return_value = (summary_text, list(cq.items)[-3:])

            results = []
            async for item in compact(cq, pool):
                results.append(item)

    # Should have saved an episodic entry
    entries = list_entries("episodic", base_dir=str(tmp_path))
    assert len(entries) == 1
    assert entries[0].content == summary_text
