from typing import Any
from pygents import ContextItem, ContextPool, ContextQueue
from pygents.registry import ToolRegistry
from pydantic import BaseModel, Field
from py_ai_toolkit import PyAIToolkit

from coder.agent.llm.prompt import build_system_prompt, LLM_VISIBLE_TOOLS
from coder.shared.console import console

TOOL_NAME_MAP = {
    "read": "tool_read",
    "write": "tool_write",
    "edit": "tool_edit",
    "bash": "tool_bash",
    "grep": "tool_grep",
    "find": "tool_find",
    "ls": "tool_ls",
}


class ToolCallRequest(BaseModel):
    """A single tool call requested by the LLM."""

    name: str = Field(
        description="Tool name: read, write, edit, bash, grep, find, or ls"
    )
    arguments: dict[str, Any] = Field(description="Arguments to pass to the tool")


class AgentResponse(BaseModel):
    """The LLM's response: either a text reply, or one or more tool calls to execute."""

    text: str | None = Field(
        None,
        description="Text response to the user. Set when no tools need to be called.",
    )
    tool_calls: list[ToolCallRequest] | None = Field(
        None,
        description="Tools to call. Set when you need to use tools before responding.",
    )


async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool by its LLM-facing name and return the result string."""
    pygents_name = TOOL_NAME_MAP.get(tool_name)
    if not pygents_name:
        return f"Error: unknown tool '{tool_name}'"

    try:
        tool_fn = ToolRegistry.get(pygents_name)
    except Exception:
        return f"Error: tool '{tool_name}' not registered"

    try:
        result = await tool_fn(**arguments)
        return str(result)
    except Exception as e:
        return f"Error executing {tool_name}: {e}"


def _build_tool_descriptions(allowed_tools: set[str] | None) -> str:
    """Build a human-readable tool reference for the system prompt."""
    tools = allowed_tools or LLM_VISIBLE_TOOLS
    descriptions = {
        "tool_read": "read(path, offset?, limit?) — Read file contents. Supports text and images. Output truncated to 2000 lines / 256KB. Use offset/limit for large files.",
        "tool_write": "write(path, content) — Write content to a file. Creates parent dirs. Use only for new files or complete rewrites.",
        "tool_edit": "edit(path, edits=[{old_text, new_text}]) — Exact text replacement. Each old_text must be unique in the file. All matches are against the original file.",
        "tool_bash": "bash(command, timeout?) — Execute a bash command. Returns stdout+stderr. Output truncated to 2000 lines / 256KB.",
        "tool_grep": "grep(pattern, path?, glob?, ignore_case?, literal?, context?, limit?) — Search file contents with ripgrep. Respects .gitignore.",
        "tool_find": "find(pattern, path?, limit?) — Find files by glob pattern with ripgrep. Respects .gitignore.",
        "tool_ls": "ls(path?, limit?) — List directory contents. Sorted alphabetically, '/' suffix for dirs.",
    }
    return "\n".join(f"- {descriptions[t]}" for t in sorted(tools) if t in descriptions)


async def run_llm_call(
    toolkit: PyAIToolkit,
    cq: ContextQueue,
    pool: ContextPool,
    allowed_tools: set[str] | None = None,
) -> None:
    """Run the LLM call loop with tool execution via asend().

    Uses py-ai-toolkit's asend() with a structured AgentResponse model.
    When the LLM requests tool calls, executes them and loops.
    When the LLM returns text, prints it and stops.

    Appends all messages (assistant + tool results) to cq.
    """
    system_prompt = build_system_prompt(pool, allowed_tools)
    tool_ref = _build_tool_descriptions(allowed_tools)

    compaction_summary = None
    try:
        summary_item = pool.get("compaction-summary")
        compaction_summary = str(summary_item.content)
    except KeyError:
        pass

    # Build the prompt with conversation history
    history_parts: list[str] = []

    if compaction_summary:
        history_parts.append(f"[Previous context]\n{compaction_summary}")

    for item in cq.items:
        if isinstance(item.content, dict):
            role = item.content.get("role", "unknown")
            content = item.content.get("content", "")
            if role == "tool":
                history_parts.append(f"[tool result]: {content}")
            elif content:
                history_parts.append(f"[{role}]: {content}")

    conversation = "\n\n".join(history_parts)

    iteration = 0
    max_iterations = 20  # safety limit

    while iteration < max_iterations:
        iteration += 1

        prompt = (
            "{{ system_prompt }}\n\n"
            "## Available Tools\n{{ tool_ref }}\n\n"
            "## Conversation\n{{ conversation }}"
        )

        response = await toolkit.asend(
            response_model=AgentResponse,
            template=prompt,
            system_prompt=system_prompt,
            tool_ref=tool_ref,
            conversation=conversation,
        )

        agent_response = response.content

        # If the LLM returned text, we're done
        if agent_response.text and not agent_response.tool_calls:
            console.response(agent_response.text)
            await cq.append(
                ContextItem(
                    content={"role": "assistant", "content": agent_response.text}
                )
            )
            return

        # Execute tool calls
        if agent_response.tool_calls:
            tool_results: list[str] = []
            for tc in agent_response.tool_calls:
                result = await execute_tool(tc.name, tc.arguments)

                display = result[:200] + "..." if len(result) > 200 else result
                context = (
                    tc.arguments.get("command")
                    or tc.arguments.get("path")
                    or tc.arguments.get("pattern")
                    or ""
                )
                console.tool_trace(tc.name, display.replace("\n", " "), context=context)

                tool_results.append(f"[tool result for {tc.name}]: {result}")

                # Append to cq
                await cq.append(
                    ContextItem(
                        content={
                            "role": "assistant",
                            "content": f"Called {tc.name}({tc.arguments})",
                        }
                    )
                )
                await cq.append(
                    ContextItem(
                        content={
                            "role": "tool",
                            "content": result,
                        }
                    )
                )

            # Append tool results to conversation for next iteration
            conversation += "\n\n" + "\n\n".join(tool_results)

        # If both text and tool_calls, print text and continue
        if agent_response.text:
            console.response(agent_response.text)
            conversation += f"\n\n[assistant]: {agent_response.text}"

        # If neither text nor tool_calls, something went wrong
        if not agent_response.text and not agent_response.tool_calls:
            console.error("No response from LLM")
            return
