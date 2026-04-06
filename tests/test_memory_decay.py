from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from coder.agent.memory.decay import group_by_age, run_decay
from coder.agent.memory.store import MemoryEntry, write_entry, list_entries


def test_group_by_age():
    now = datetime.now(timezone.utc)
    entries = [
        MemoryEntry(
            type="episodic",
            topic="recent",
            content="A",
            created=now - timedelta(days=1),
        ),
        MemoryEntry(
            type="episodic",
            topic="weekly",
            content="B",
            created=now - timedelta(days=10),
        ),
        MemoryEntry(
            type="episodic",
            topic="monthly",
            content="C",
            created=now - timedelta(days=40),
        ),
    ]
    recent, to_weekly, to_monthly = group_by_age(entries, now=now)
    assert len(recent) == 1
    assert recent[0].topic == "recent"
    assert len(to_weekly) == 1
    assert to_weekly[0].topic == "weekly"
    assert len(to_monthly) == 1
    assert to_monthly[0].topic == "monthly"


def test_group_by_age_skips_already_decayed():
    now = datetime.now(timezone.utc)
    entries = [
        MemoryEntry(
            type="episodic",
            topic="week-2026-W10",
            content="Already merged",
            created=now - timedelta(days=15),
            decay="weekly",
        ),
    ]
    recent, to_weekly, to_monthly = group_by_age(entries, now=now)
    assert len(recent) == 0
    assert len(to_weekly) == 0
    assert len(to_monthly) == 0


@pytest.mark.asyncio
async def test_run_decay_merges_weekly(tmp_path):
    now = datetime.now(timezone.utc)
    for i in range(3):
        write_entry(
            MemoryEntry(
                type="episodic",
                topic=f"old-{i}",
                content=f"Session {i} summary.",
                created=now - timedelta(days=10 + i),
            ),
            base_dir=str(tmp_path),
        )

    toolkit = MagicMock()
    response = MagicMock()
    response.content = "Merged weekly summary."
    toolkit.chat = AsyncMock(return_value=response)

    await run_decay(toolkit, base_dir=str(tmp_path), now=now)

    entries = list_entries("episodic", base_dir=str(tmp_path))
    # Original 3 should be replaced by 1 weekly summary
    assert len(entries) == 1
    assert entries[0].decay == "weekly"
    assert entries[0].content == "Merged weekly summary."


@pytest.mark.asyncio
async def test_run_decay_no_entries(tmp_path):
    toolkit = MagicMock()
    # Should not raise
    await run_decay(toolkit, base_dir=str(tmp_path))
