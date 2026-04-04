# coder/agent/llm/decide.py
from typing import Any

from pydantic import BaseModel, Field
from pygents import ContextPool


class ToolCallRequest(BaseModel):
    """A single tool call requested by the LLM."""
    name: str = Field(description="Tool name (e.g. tool_read, tool_write)")
    arguments: dict[str, Any] = Field(description="Arguments to pass to the tool")


class AgentResponse(BaseModel):
    """The LLM's response: either a text reply, or one or more tool calls."""
    text: str | None = Field(None, description="Text response to the user. Set when no tools need to be called.")
    tool_calls: list[ToolCallRequest] | None = Field(None, description="Tools to call. Set when you need to use tools before responding.")


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
