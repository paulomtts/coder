# coder/agent/llm/decide.py
from typing import Any

from pydantic import BaseModel, Field


class ToolCallRequest(BaseModel):
    """A single tool call requested by the LLM."""

    name: str = Field(description="Tool name (e.g. tool_read, tool_write)")
    arguments: dict[str, Any] = Field(description="Arguments to pass to the tool")


class AgentResponse(BaseModel):
    """The LLM's decision: which tools to call next, if any.

    This is a routing decision, not a user-facing response. If no tools are
    needed, return an empty tool_calls list — a separate streaming call will
    generate the actual response."""

    tool_calls: list[ToolCallRequest] = Field(
        default_factory=list,
        description="Tools to call. Leave empty when no tools are needed and the conversation can proceed to a direct response.",
    )
