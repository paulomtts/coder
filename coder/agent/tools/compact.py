# coder/agent/tools/compact.py
from datetime import datetime, timezone

from pygents import ContextItem, ContextPool, ContextQueue, tool

from coder.agent.compaction.summarizer import run_compaction
from coder.agent.llm.prompt import get_compaction_summary
from coder.agent.memory.store import MemoryEntry, write_entry
from coder.agent.state import get_session
from coder.shared.console import dbg


@tool()
async def compact(cq: ContextQueue, pool: ContextPool):
    """Compact the context queue by summarizing old messages.

    NOTE: This tool directly manipulates cq (clear + re-add) because pygents
    routing only supports append — there is no routing path for clearing a queue.
    The summary ContextItem is routed to the pool via normal yield mechanics.
    """
    session = get_session()
    existing_summary = get_compaction_summary(pool)

    dbg("COMPACT", f"compacting {len(cq.items)} items", "33")

    summary, recent = await run_compaction(
        session.toolkit, cq.items, existing_summary, session.config.keep_recent_tokens
    )

    # Clear queue and re-add only recent items (direct manipulation — unavoidable)
    await cq.clear()
    for item in recent:
        await cq.append(item)

    dbg("COMPACT", f"kept {len(recent)} recent items", "33")

    # Save episodic memory entry
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    write_entry(
        MemoryEntry(
            type="episodic",
            topic=timestamp,
            content=summary,
            tags=[],
        ),
        base_dir=session.config.memory_dir,
    )
    dbg("COMPACT", f"saved episodic entry: {timestamp}", "32")

    # Route summary to pool via normal ContextItem yield (agent stores it)
    yield ContextItem(
        id="compaction-summary",
        description="Compacted conversation summary",
        content=summary,
    )
