import os
from typing import TypedDict
from pygents import tool


class EditEntry(TypedDict):
    old_text: str
    new_text: str


@tool()
async def tool_edit(path: str, edits: list[EditEntry]) -> str:
    """Edit a single file using exact text replacement."""
    try:
        if not os.path.exists(path):
            return f"Error: file not found: {path}"
        with open(path, "r", encoding="utf-8") as f:
            original = f.read()
        replacements: list[tuple[int, int, str]] = []
        for i, edit in enumerate(edits):
            old = edit["old_text"]
            count = original.count(old)
            if count == 0:
                return f"Error: edit {i + 1} old_text not found in {path}"
            if count > 1:
                return f"Error: edit {i + 1} old_text matches multiple locations in {path}. Make it more specific."
            start = original.index(old)
            end = start + len(old)
            replacements.append((start, end, edit["new_text"]))
        replacements.sort(key=lambda r: r[0])
        for j in range(len(replacements) - 1):
            if replacements[j][1] > replacements[j + 1][0]:
                return f"Error: edits overlap in {path}"
        result = original
        for start, end, new_text in reversed(replacements):
            result = result[:start] + new_text + result[end:]
        with open(path, "w", encoding="utf-8") as f:
            f.write(result)
        return f"Applied {len(edits)} edit(s) to {path}"
    except Exception as e:
        return f"Error editing {path}: {e}"
