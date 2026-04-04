import os
from pygents import ContextItem, tool
from coder.shared.constants import LS_MAX_ENTRIES, MAX_BYTES


@tool()
async def tool_ls(path: str | None = None, limit: int | None = None):
    """List directory contents. Sorted alphabetically, '/' suffix for dirs. Includes dotfiles."""
    target = path if path else os.getcwd()
    max_entries = limit if limit is not None else LS_MAX_ENTRIES
    try:
        if not os.path.isdir(target):
            yield ContextItem(content={"role": "tool", "content": f"Error: not a directory: {target}"})
            return
        entries = sorted(os.listdir(target))
        formatted = []
        for entry in entries:
            full = os.path.join(target, entry)
            if os.path.isdir(full):
                formatted.append(f"{entry}/")
            else:
                formatted.append(entry)
        truncated = False
        if len(formatted) > max_entries:
            formatted = formatted[:max_entries]
            truncated = True
        result = "\n".join(formatted)
        if len(result.encode("utf-8", errors="replace")) > MAX_BYTES:
            encoded = result.encode("utf-8", errors="replace")[:MAX_BYTES]
            result = encoded.decode("utf-8", errors="replace")
            truncated = True
        if truncated:
            result += f"\n\n[Listing truncated. Limit: {max_entries} entries]"
        yield ContextItem(content={"role": "tool", "content": result})
    except Exception as e:
        yield ContextItem(content={"role": "tool", "content": f"Error listing {target}: {e}"})
