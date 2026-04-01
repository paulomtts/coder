import asyncio
from pygents import tool
from coder.constants import FIND_MAX_RESULTS, MAX_BYTES

@tool()
async def tool_find(pattern: str, path: str | None = None, limit: int | None = None) -> str:
    """Search for files by glob pattern using ripgrep."""
    args = ["rg", "--files", "--glob", pattern, "--color=never"]
    if path: args.append(path)
    max_results = limit if limit is not None else FIND_MAX_RESULTS
    try:
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace")
        if not output.strip(): return "No matches found."
        lines = output.strip().split("\n")
        truncated = False
        if len(lines) > max_results:
            lines = lines[:max_results]
            truncated = True
        result = "\n".join(lines)
        if len(result.encode("utf-8", errors="replace")) > MAX_BYTES:
            encoded = result.encode("utf-8", errors="replace")[:MAX_BYTES]
            result = encoded.decode("utf-8", errors="replace")
            truncated = True
        if truncated:
            result += f"\n\n[Results truncated. Limit: {max_results} files]"
        return result
    except FileNotFoundError:
        return "Error: 'rg' (ripgrep) is not installed."
    except Exception as e:
        return f"Error running find: {e}"
