import sys
from typing import Any
from pygents import ContextItem, ContextPool, ContextQueue, Turn, tool
from pygents.registry import ToolRegistry

LLM_VISIBLE_TOOLS = {"tool_read", "tool_write", "tool_edit", "tool_bash", "tool_grep", "tool_find", "tool_ls"}
GUIDELINE_BASH_ONLY = "Use bash for file operations like ls, rg, find"
GUIDELINE_PREFER_TOOLS = "Prefer grep/find/ls tools over bash for file exploration (faster, respects .gitignore)"
GUIDELINE_CONCISE = "Be concise in your responses"
GUIDELINE_FILE_PATHS = "Show file paths clearly when working with files"

def _build_guidelines(allowed_tools: set[str] | None) -> str:
    tools = allowed_tools or LLM_VISIBLE_TOOLS
    guidelines = []
    has_bash = "tool_bash" in tools
    has_search_tools = "tool_grep" in tools or "tool_find" in tools or "tool_ls" in tools
    if has_bash and has_search_tools:
        guidelines.append(GUIDELINE_PREFER_TOOLS)
    elif has_bash:
        guidelines.append(GUIDELINE_BASH_ONLY)
    if "tool_read" in tools:
        guidelines.append("Use read to examine files instead of cat or sed.")
    if "tool_write" in tools:
        guidelines.append("Use write only for new files or complete rewrites.")
    if "tool_edit" in tools:
        guidelines.extend([
            "Use edit for precise changes (edits[].oldText must match exactly)",
            "When changing multiple separate locations in one file, use one edit call with multiple entries in edits[] instead of multiple edit calls",
            "Each edits[].oldText is matched against the original file, not after earlier edits are applied. Do not emit overlapping or nested edits. Merge nearby changes into one edit.",
            "Keep edits[].oldText as small as possible while still being unique in the file. Do not pad with large unchanged regions.",
        ])
    guidelines.append(GUIDELINE_CONCISE)
    guidelines.append(GUIDELINE_FILE_PATHS)
    return "\n".join(f"- {g}" for g in guidelines)

def _build_tools_list(allowed_tools: set[str] | None) -> str:
    tools = allowed_tools or LLM_VISIBLE_TOOLS
    snippets = {
        "tool_read": "read: Read file contents",
        "tool_write": "write: Create or overwrite files",
        "tool_edit": "edit: Make precise file edits with exact text replacement",
        "tool_bash": "bash: Execute bash commands",
        "tool_grep": "grep: Search file contents for patterns (respects .gitignore)",
        "tool_find": "find: Find files by glob pattern (respects .gitignore)",
        "tool_ls": "ls: List directory contents",
    }
    return "\n".join(f"- {snippets[t]}" for t in sorted(tools) if t in snippets)

def build_system_prompt(pool: ContextPool, allowed_tools: set[str] | None, tools_list: str | None = None) -> str:
    parts: list[str] = []
    base_item = pool._items.get("base-prompt")
    if base_item:
        base = str(base_item.content)
        tl = tools_list or _build_tools_list(allowed_tools)
        guidelines = _build_guidelines(allowed_tools)
        base = base.replace("{tools_list}", tl)
        base = base.replace("{guidelines}", guidelines)
        parts.append(base)
    role_item = pool._items.get("active-role")
    if role_item:
        parts.append(str(role_item.content))
    ctx_item = pool._items.get("project-context")
    if ctx_item and str(ctx_item.content).strip():
        parts.append(str(ctx_item.content))
    skills_item = pool._items.get("skills-index")
    if skills_item and str(skills_item.content).strip():
        parts.append(str(skills_item.content))
    append_item = pool._items.get("append-prompt")
    if append_item and str(append_item.content).strip():
        parts.append(str(append_item.content))
    return "\n\n".join(parts)

def build_messages(cq: ContextQueue, compaction_summary: str | None = None) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if compaction_summary:
        messages.append({"role": "system", "content": f"[Context from previous conversation]\n{compaction_summary}"})
    for item in cq.items:
        if isinstance(item.content, dict):
            messages.append(item.content)
    return messages

def build_tool_schemas(allowed_tools: set[str] | None) -> list[dict[str, Any]]:
    tools = allowed_tools or LLM_VISIBLE_TOOLS
    schemas = []
    for t in ToolRegistry.all():
        if t.__name__ not in tools:
            continue
        name = t.__name__[5:] if t.__name__.startswith("tool_") else t.__name__
        schema: dict[str, Any] = {"type": "function", "function": {"name": name, "description": t.metadata.description or ""}}
        if t.metadata.input_schema:
            schema["function"]["parameters"] = t.metadata.input_schema
        schemas.append(schema)
    return schemas

TOOL_NAME_MAP = {
    "read": "tool_read", "write": "tool_write", "edit": "tool_edit",
    "bash": "tool_bash", "grep": "tool_grep", "find": "tool_find", "ls": "tool_ls",
}

from pydantic import BaseModel, Field

from py_ai_toolkit import PyAIToolkit


class ToolCallRequest(BaseModel):
    """A single tool call requested by the LLM."""
    name: str = Field(description="Tool name: read, write, edit, bash, grep, find, or ls")
    arguments: dict[str, Any] = Field(description="Arguments to pass to the tool")


class AgentResponse(BaseModel):
    """The LLM's response: either a text reply, or one or more tool calls to execute."""
    text: str | None = Field(None, description="Text response to the user. Set when no tools need to be called.")
    tool_calls: list[ToolCallRequest] | None = Field(None, description="Tools to call. Set when you need to use tools before responding.")


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
            print(agent_response.text)
            await cq.append(ContextItem(content={"role": "assistant", "content": agent_response.text}))
            return

        # Execute tool calls
        if agent_response.tool_calls:
            tool_results: list[str] = []
            for tc in agent_response.tool_calls:
                print(f"  [{tc.name}] ", end="", flush=True)
                result = await execute_tool(tc.name, tc.arguments)

                display = result[:200] + "..." if len(result) > 200 else result
                print(display.replace("\n", " "))

                tool_results.append(f"[tool result for {tc.name}]: {result}")

                # Append to cq
                await cq.append(ContextItem(content={
                    "role": "assistant",
                    "content": f"Called {tc.name}({tc.arguments})",
                }))
                await cq.append(ContextItem(content={
                    "role": "tool",
                    "content": result,
                }))

            # Append tool results to conversation for next iteration
            conversation += "\n\n" + "\n\n".join(tool_results)

        # If both text and tool_calls, print text and continue
        if agent_response.text:
            print(agent_response.text)
            conversation += f"\n\n[assistant]: {agent_response.text}"

        # If neither text nor tool_calls, something went wrong
        if not agent_response.text and not agent_response.tool_calls:
            print("[No response from LLM]")
            return
