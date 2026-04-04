# coder/agent/llm/decide.py
from typing import Any

from pydantic import BaseModel, Field
from pygents import ContextPool


class ToolCallRequest(BaseModel):
    """A single tool call requested by the LLM."""

    name: str = Field(description="Tool name (e.g. tool_read, tool_write)")
    arguments: dict[str, Any] = Field(description="Arguments to pass to the tool")


class AgentResponse(BaseModel):
    """The LLM's response: either a text reply, or one or more tool calls.

    IMPORTANT: Always prefer tool_calls over text when answering questions about
    the codebase. Use tools to read, search, or inspect before responding.
    Only use text alone for trivial follow-ups or when all needed context is
    already in the conversation."""

    text: str | None = Field(
        None,
        description="Final text response to the user. Only set this WITHOUT tool_calls when you already have all the information needed to answer. Do not use this to narrate intent — call tools instead.",
    )
    tool_calls: list[ToolCallRequest] | None = Field(
        None,
        description="Tools to call before responding. Always use this when you need to read files, search code, run commands, or verify anything in the codebase. You can set text alongside tool_calls for brief status notes.",
    )


def get_allowed_tools(pool: ContextPool) -> set[str] | None:
    try:
        item = pool.get("allowed-tools")
        tools = item.content
        if isinstance(tools, set):
            return tools
        return None
    except KeyError:
        return None


def get_compaction_summary(pool: ContextPool) -> str | None:
    try:
        item = pool.get("compaction-summary")
        return str(item.content)
    except KeyError:
        return None
