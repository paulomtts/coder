# coder/agent/hooks.py
from pygents import Agent, ContextItem, Turn


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
