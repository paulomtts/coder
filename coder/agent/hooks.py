# coder/agent/hooks.py
from pygents import Agent, ContextItem, Turn

from coder.agent.memory.extraction import extract_semantic_facts
from coder.agent.memory.store import (
    MemoryEntry,
    build_memory_index,
    write_entry,
)
from coder.agent.state import get_session


INTERNAL_TOOLS = {"llm_decide", "llm_respond", "compact"}


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
        result_preview[:200] + "..." if len(result_preview) > 200 else result_preview
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


async def extract_memories(agent: Agent, turn: Turn) -> None:
    """After-turn hook: extract semantic facts from llm_respond turns."""
    raw_name = turn.tool.metadata.name
    if raw_name != "llm_respond":
        return

    session = get_session()
    memory_dir = session.config.memory_dir

    # Get the latest assistant response from the turn output
    assistant_content = ""
    if isinstance(turn.output, list):
        for item in turn.output:
            if isinstance(item, ContextItem) and isinstance(item.content, dict):
                assistant_content = item.content.get("content", "")
                break

    # Get latest user message from the context queue
    user_content = ""
    for item in reversed(list(agent.context_queue.items)):
        if isinstance(item.content, dict) and item.content.get("role") == "user":
            user_content = item.content.get("content", "")
            break

    if not user_content and not assistant_content:
        return

    turn_content = f"User: {user_content}\nAssistant: {assistant_content}"
    existing_memories = build_memory_index(base_dir=memory_dir)

    try:
        facts = await extract_semantic_facts(
            session.toolkit, turn_content, existing_memories, ""
        )
    except Exception:
        return

    if not facts:
        return

    for fact in facts:
        write_entry(
            MemoryEntry(
                type="semantic",
                topic=fact.topic,
                content=fact.content,
                tags=[],
            ),
            base_dir=memory_dir,
        )

    # Update the semantic-memory pool item so current session sees changes
    updated_index = build_memory_index(base_dir=memory_dir)
    try:
        await agent.context_pool.remove("semantic-memory")
    except KeyError:
        pass
    await agent.context_pool.add(
        ContextItem(
            id="semantic-memory",
            description="Persistent semantic memory",
            content=updated_index,
        )
    )
