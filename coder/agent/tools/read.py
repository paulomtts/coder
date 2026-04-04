import base64
import os
from pygents import ContextItem, tool
from coder.shared.constants import MAX_BYTES, MAX_LINES

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _truncate_output(content: str, max_lines: int, max_bytes: int) -> str:
    lines = content.split("\n")
    truncated = False
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        truncated = True
    result = "\n".join(lines)
    if len(result.encode("utf-8", errors="replace")) > max_bytes:
        encoded = result.encode("utf-8", errors="replace")[:max_bytes]
        result = encoded.decode("utf-8", errors="replace")
        truncated = True
    if truncated:
        result += (
            f"\n\n[Output truncated. Limits: {max_lines} lines, {max_bytes // 1024}KB]"
        )
    return result


@tool()
async def tool_read(
    path: str, offset: int | None = None, limit: int | None = None
):
    """Read the contents of a file. Supports text files and images."""
    try:
        if not os.path.exists(path):
            yield ContextItem(content={"role": "tool", "content": f"Error: file not found: {path}"})
            return
        ext = os.path.splitext(path)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            yield ContextItem(content={"role": "tool", "content": f"[Image: {path}]\nBase64: {data}"})
            return
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if offset is not None:
            start = max(0, offset - 1)
            lines = lines[start:]
        if limit is not None:
            lines = lines[:limit]
        content = "".join(lines)
        yield ContextItem(content={"role": "tool", "content": _truncate_output(content, MAX_LINES, MAX_BYTES)})
    except Exception as e:
        yield ContextItem(content={"role": "tool", "content": f"Error reading {path}: {e}"})
