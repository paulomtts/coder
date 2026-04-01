import os
from pygents import tool


@tool()
async def tool_write(path: str, content: str) -> str:
    """Write content to a file. Creates the file if it doesn't exist, overwrites if it does. Automatically creates parent directories."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"
