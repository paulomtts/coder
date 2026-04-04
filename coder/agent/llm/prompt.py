from typing import Any
from pygents import ContextPool, ContextQueue
from pygents.registry import ToolRegistry

LLM_VISIBLE_TOOLS = {
    "tool_read",
    "tool_write",
    "tool_edit",
    "tool_bash",
    "tool_grep",
    "tool_find",
    "tool_ls",
}
GUIDELINE_BASH_ONLY = "Use bash for file operations like ls, rg, find"
GUIDELINE_PREFER_TOOLS = "Prefer grep/find/ls tools over bash for file exploration (faster, respects .gitignore)"
GUIDELINE_TOOLS_FIRST = "Always use tools to ground your answers in actual code and project state. Never answer from assumptions or prior knowledge when you can read, grep, or list files instead."
GUIDELINE_CONCISE = "Be concise in your responses"
GUIDELINE_FILE_PATHS = "Show file paths clearly when working with files"


def _build_guidelines(allowed_tools: set[str] | None) -> str:
    tools = allowed_tools or LLM_VISIBLE_TOOLS
    guidelines = [GUIDELINE_TOOLS_FIRST]
    has_bash = "tool_bash" in tools
    has_search_tools = (
        "tool_grep" in tools or "tool_find" in tools or "tool_ls" in tools
    )
    if has_bash and has_search_tools:
        guidelines.append(GUIDELINE_PREFER_TOOLS)
    elif has_bash:
        guidelines.append(GUIDELINE_BASH_ONLY)
    if "tool_read" in tools:
        guidelines.append("Use read to examine files instead of cat or sed.")
    if "tool_write" in tools:
        guidelines.append("Use write only for new files or complete rewrites.")
    if "tool_edit" in tools:
        guidelines.extend(
            [
                "Use edit for precise changes (edits[].oldText must match exactly)",
                "When changing multiple separate locations in one file, use one edit call with multiple entries in edits[] instead of multiple edit calls",
                "Each edits[].oldText is matched against the original file, not after earlier edits are applied. Do not emit overlapping or nested edits. Merge nearby changes into one edit.",
                "Keep edits[].oldText as small as possible while still being unique in the file. Do not pad with large unchanged regions.",
            ]
        )
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


def build_system_prompt(
    pool: ContextPool, allowed_tools: set[str] | None, tools_list: str | None = None
) -> str:
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


def build_messages(
    cq: ContextQueue, compaction_summary: str | None = None
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if compaction_summary:
        messages.append(
            {
                "role": "system",
                "content": f"[Context from previous conversation]\n{compaction_summary}",
            }
        )
    for item in cq.items:
        if isinstance(item.content, dict):
            messages.append(item.content)
    return messages


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


def build_conversation(messages: list[dict]) -> str:
    """Build a conversation string from a list of message dicts."""
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if content:
            parts.append(f"[{role}]: {content}")
    return "\n\n".join(parts)


def build_tool_schemas(allowed_tools: set[str] | None) -> list[dict[str, Any]]:
    tools = allowed_tools or LLM_VISIBLE_TOOLS
    schemas = []
    for t in ToolRegistry.all():
        if t.__name__ not in tools:
            continue
        name = t.__name__[5:] if t.__name__.startswith("tool_") else t.__name__
        schema: dict[str, Any] = {
            "type": "function",
            "function": {"name": name, "description": t.metadata.description or ""},
        }
        if t.metadata.input_schema:
            schema["function"]["parameters"] = t.metadata.input_schema
        schemas.append(schema)
    return schemas
