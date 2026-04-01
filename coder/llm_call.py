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

import json

from py_ai_toolkit import PyAIToolkit


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


async def run_llm_call(
    toolkit: PyAIToolkit,
    cq: ContextQueue,
    pool: ContextPool,
    allowed_tools: set[str] | None = None,
) -> None:
    """Run the LLM call loop with tool execution.

    Streams text to stdout. When the LLM requests tool calls, executes them
    and sends results back in a loop until the LLM produces a final text
    response (no more tool calls).

    Appends all messages (assistant + tool results) to cq as it goes.
    """
    system_prompt = build_system_prompt(pool, allowed_tools)

    compaction_summary = None
    try:
        summary_item = pool.get("compaction-summary")
        compaction_summary = str(summary_item.content)
    except KeyError:
        pass

    # Build initial messages with system prompt
    api_messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

    if compaction_summary:
        api_messages.append({
            "role": "system",
            "content": f"[Context from previous conversation]\n{compaction_summary}",
        })

    # Add conversation history
    for item in cq.items:
        if isinstance(item.content, dict):
            api_messages.append(item.content)

    # Build tool schemas
    tool_schemas = build_tool_schemas(allowed_tools)

    # Get the raw OpenAI client and model
    client = toolkit.llm_client.openai_client
    model = toolkit.llm_client._model

    while True:
        # Call LLM with streaming
        create_kwargs: dict[str, Any] = {
            "model": model,
            "messages": api_messages,
            "stream": True,
        }
        if tool_schemas:
            create_kwargs["tools"] = tool_schemas
            create_kwargs["tool_choice"] = "auto"

        stream = await client.chat.completions.create(**create_kwargs)

        # Accumulate the streamed response
        full_text = ""
        tool_calls_by_index: dict[int, dict[str, Any]] = {}

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # Stream text content to stdout
            if delta.content:
                sys.stdout.write(delta.content)
                sys.stdout.flush()
                full_text += delta.content

            # Accumulate tool call deltas
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_by_index:
                        tool_calls_by_index[idx] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    tc = tool_calls_by_index[idx]
                    if tc_delta.id:
                        tc["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tc["function"]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc["function"]["arguments"] += tc_delta.function.arguments

        if full_text:
            print()  # newline after streamed text

        # Build the assistant message
        assistant_msg: dict[str, Any] = {"role": "assistant"}
        if full_text:
            assistant_msg["content"] = full_text
        if tool_calls_by_index:
            assistant_msg["tool_calls"] = [
                tool_calls_by_index[i] for i in sorted(tool_calls_by_index)
            ]

        # Append assistant message to context and API messages
        await cq.append(ContextItem(content=assistant_msg))
        api_messages.append(assistant_msg)

        # If no tool calls, we're done
        if not tool_calls_by_index:
            break

        # Execute each tool call and append results
        for idx in sorted(tool_calls_by_index):
            tc = tool_calls_by_index[idx]
            fn_name = tc["function"]["name"]
            try:
                fn_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                fn_args = {}

            print(f"  [{fn_name}] ", end="", flush=True)
            result = await execute_tool(fn_name, fn_args)

            # Truncate display of tool result
            display = result[:200] + "..." if len(result) > 200 else result
            print(display.replace("\n", " "))

            tool_result_msg = {
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            }
            await cq.append(ContextItem(content=tool_result_msg))
            api_messages.append(tool_result_msg)

        # Loop back to call LLM again with tool results
