import os
from pygents import ContextItem, tool


@tool()
async def tool_write(path: str, content: str):
    """Write content to a file. Creates the file if it doesn't exist, overwrites if it does. Automatically creates parent directories."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        yield ContextItem(content={"role": "tool", "content": f"Wrote {len(content)} bytes to {path}"})
    except Exception as e:
        yield ContextItem(content={"role": "tool", "content": f"Error writing {path}: {e}"})
