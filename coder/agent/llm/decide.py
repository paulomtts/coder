# coder/agent/llm/decide.py
from typing import Any

from pydantic import BaseModel, Field
from pygents import ContextItem, ContextPool, ContextQueue, Turn, tool
from py_ai_toolkit import PyAIToolkit

from coder.agent.llm.prompt import build_system_prompt, build_messages, build_tool_schemas


class ToolCallRequest(BaseModel):
    """A single tool call requested by the LLM."""
    name: str = Field(description="Tool name (e.g. tool_read, tool_write)")
    arguments: dict[str, Any] = Field(description="Arguments to pass to the tool")


class AgentResponse(BaseModel):
    """The LLM's response: either a text reply, or one or more tool calls."""
    text: str | None = Field(None, description="Text response to the user. Set when no tools need to be called.")
    tool_calls: list[ToolCallRequest] | None = Field(None, description="Tools to call. Set when you need to use tools before responding.")


@tool()
async def llm_decide(cq: ContextQueue, pool: ContextPool, toolkit: PyAIToolkit):
    """Structured LLM call that decides: execute tools or respond to user."""
    allowed_tools = _get_allowed_tools(pool)
    system_prompt = build_system_prompt(pool, allowed_tools)
    compaction_summary = _get_compaction_summary(pool)
    messages = build_messages(cq, compaction_summary)
    tool_schemas = build_tool_schemas(allowed_tools)

    # Build conversation string from messages
    history_parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if content:
            history_parts.append(f"[{role}]: {content}")
    conversation = "\n\n".join(history_parts)

    # Build tool reference string
    tool_ref = "\n".join(
        f"- {s['function']['name']}: {s['function'].get('description', '')}"
        for s in tool_schemas
    )

    # Structured LLM call
    response = await toolkit.asend(
        response_model=AgentResponse,
        template=(
            "{{ system_prompt }}\n\n"
            "## Available Tools\n{{ tool_ref }}\n\n"
            "## Conversation\n{{ conversation }}"
        ),
        system_prompt=system_prompt,
        tool_ref=tool_ref,
        conversation=conversation,
    )

    agent_response = response.content

    assistant_content = ""
    if agent_response.text:
        assistant_content = agent_response.text
    if agent_response.tool_calls:
        calls_desc = ", ".join(
            f"{tc.name}({tc.arguments})" for tc in agent_response.tool_calls
        )
        assistant_content = (
            f"{assistant_content}\nCalling: {calls_desc}" if assistant_content else f"Calling: {calls_desc}"
        )

    # Yield assistant message -> agent routes to cq
    yield ContextItem(content={"role": "assistant", "content": assistant_content})

    # Route next step
    if agent_response.tool_calls:
        for tc in agent_response.tool_calls:
            yield Turn(tc.name, kwargs=tc.arguments)
        yield Turn(llm_decide)
    else:
        from coder.agent.llm.respond import llm_respond
        yield Turn(llm_respond)


def _get_allowed_tools(pool: ContextPool) -> set[str] | None:
    try:
        item = pool.get("allowed-tools")
        tools = item.content
        if isinstance(tools, set):
            return tools
        return None
    except KeyError:
        return None


def _get_compaction_summary(pool: ContextPool) -> str | None:
    try:
        item = pool.get("compaction-summary")
        return str(item.content)
    except KeyError:
        return None
