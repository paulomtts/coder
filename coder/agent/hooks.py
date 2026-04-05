# coder/agent/hooks.py
import asyncio

from pygents import Agent, ContextItem, ContextPool, ContextQueue, Turn

from coder.agent.compaction.summarizer import run_compaction, should_compact
from coder.agent.state import get_session


INTERNAL_TOOLS = {"llm_decide", "llm_respond"}


async def inject_steering(agent: Agent) -> None:
    """Before-turn hook: inject steering messages before llm_decide turns."""
    turn = agent._current_turn
    if turn is None or turn.tool.metadata.name != "llm_decide":
        return
    session = get_session()
    while not session.steering_queue.empty():
        try:
            msg = session.steering_queue.get_nowait()
            await agent.context_queue.append(
                ContextItem(content={"role": "user", "content": msg})
            )
        except asyncio.QueueEmpty:
            break


async def check_compaction(cq: ContextQueue, pool: ContextPool) -> None:
    """Before-invoke hook on llm_decide: compact context if needed."""
    session = get_session()
    toolkit = session.toolkit
    items = cq.items
    max_tokens = 128_000
    if not should_compact(items, session.config.compaction_threshold, max_tokens):
        return
    existing_summary = None
    try:
        summary_item = pool.get("compaction-summary")
        existing_summary = str(summary_item.content)
    except KeyError:
        pass
    summary, recent = await run_compaction(
        toolkit, items, existing_summary, session.config.keep_recent_tokens
    )
    try:
        await pool.remove("compaction-summary")
    except KeyError:
        pass
    await pool.add(
        ContextItem(
            id="compaction-summary",
            description="Compacted conversation summary",
            content=summary,
        )
    )
    await cq.clear()
    for item in recent:
        await cq.append(item)


async def trace_tool(agent: Agent, turn: Turn) -> None:
    """After-turn hook: show tool traces for non-internal tools."""
    from coder.shared.console import console

    raw_name = turn.tool.metadata.name
    if raw_name in INTERNAL_TOOLS:
        return
    result_preview = ""
    if isinstance(turn.output, list):
        for item in turn.output:
            if isinstance(item, ContextItem) and isinstance(item.content, dict):
                result_preview = str(item.content.get("content", ""))
                break
    display = (
        result_preview[:200] + "..."
        if len(result_preview) > 200
        else result_preview
    )
    display = display.replace("\n", " ")
    context = (
        turn.kwargs.get("command")
        or turn.kwargs.get("path")
        or turn.kwargs.get("pattern")
        or ""
    )
    display_name = raw_name[5:] if raw_name.startswith("tool_") else raw_name
    console.tool_trace(display_name, display, context=context)
