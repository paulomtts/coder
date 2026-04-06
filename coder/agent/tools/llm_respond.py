# coder/agent/tools/llm_respond.py
from pygents import ContextItem, ContextPool, ContextQueue, tool

from coder.agent.llm.prompt import (
    build_conversation,
    build_messages,
    build_system_prompt,
    get_compaction_summary,
)
from coder.agent.state import get_session
from coder.shared.console import dbg


@tool()
async def llm_respond(cq: ContextQueue, pool: ContextPool):
    """Streaming LLM call that yields text chunks for the REPL to print."""
    dbg("RESPOND", f"entering llm_respond, cq has {len(list(cq.items))} items", "35")
    session = get_session()
    toolkit = session.toolkit
    allowed_tools = session._allowed_tools
    system_prompt = build_system_prompt(pool, allowed_tools)
    compaction_summary = get_compaction_summary(pool)
    messages_list = build_messages(cq, compaction_summary)

    conversation = build_conversation(messages_list)

    # Streaming LLM call (no tool schemas — text only)
    full_text = ""
    last_chunk = None
    async for chunk in toolkit.stream(
        template="{{ system_prompt }}\n\n## Conversation\n{{ conversation }}",
        system_prompt=system_prompt,
        conversation=conversation,
    ):
        full_text += chunk.content
        last_chunk = chunk
        yield chunk.content

    # Record token usage from last chunk (if available)
    if last_chunk:
        usage = getattr(last_chunk.completion, "usage", None)
        if usage:
            session.token_stats.record(
                prompt_tokens=usage.prompt_tokens or 0,
                completion_tokens=usage.completion_tokens or 0,
            )

    # Yield full assistant message -> agent routes to cq
    yield ContextItem(content={"role": "assistant", "content": full_text})
