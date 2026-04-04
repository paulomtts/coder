# coder/agent/llm/respond.py
from pygents import ContextItem, ContextPool, ContextQueue, tool
from py_ai_toolkit import PyAIToolkit

from coder.agent.llm.prompt import build_system_prompt, build_messages


@tool()
async def llm_respond(cq: ContextQueue, pool: ContextPool, toolkit: PyAIToolkit):
    """Streaming LLM call that yields text chunks for the REPL to print."""
    from coder.agent.llm.decide import _get_allowed_tools, _get_compaction_summary

    allowed_tools = _get_allowed_tools(pool)
    system_prompt = build_system_prompt(pool, allowed_tools)
    compaction_summary = _get_compaction_summary(pool)
    messages = build_messages(cq, compaction_summary)

    # Build conversation string from messages
    history_parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if content:
            history_parts.append(f"[{role}]: {content}")
    conversation = "\n\n".join(history_parts)

    # Streaming LLM call (no tool schemas — text only)
    full_text = ""
    async for chunk in toolkit.stream(
        template="{{ system_prompt }}\n\n## Conversation\n{{ conversation }}",
        system_prompt=system_prompt,
        conversation=conversation,
    ):
        full_text += chunk.content
        yield chunk.content

    # Yield full assistant message -> agent routes to cq
    yield ContextItem(content={"role": "assistant", "content": full_text})
