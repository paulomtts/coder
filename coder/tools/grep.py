# coder/tools/grep.py
import asyncio
from pygents import tool
from coder.constants import GREP_MAX_LINE_LENGTH, GREP_MAX_MATCHES, MAX_BYTES

@tool()
async def tool_grep(pattern: str, path: str | None = None, glob: str | None = None, ignore_case: bool = False, literal: bool = False, context: int | None = None, limit: int | None = None) -> str:
    """Search file contents for a pattern using ripgrep."""
    args = ["rg", "--no-heading", "--line-number", "--color=never"]
    if ignore_case: args.append("-i")
    if literal: args.append("-F")
    if context is not None: args.extend(["-C", str(context)])
    if glob is not None: args.extend(["--glob", glob])
    max_matches = limit if limit is not None else GREP_MAX_MATCHES
    args.extend(["-m", str(max_matches)])
    args.append(pattern)
    if path: args.append(path)
    try:
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace")
        if not output.strip(): return "No matches found."
        lines = output.split("\n")
        lines = [line[:GREP_MAX_LINE_LENGTH] + "..." if len(line) > GREP_MAX_LINE_LENGTH else line for line in lines]
        output = "\n".join(lines)
        if len(output.encode("utf-8", errors="replace")) > MAX_BYTES:
            encoded = output.encode("utf-8", errors="replace")[:MAX_BYTES]
            output = encoded.decode("utf-8", errors="replace")
            output += f"\n\n[Output truncated at {MAX_BYTES // 1024}KB]"
        return output
    except FileNotFoundError:
        return "Error: 'rg' (ripgrep) is not installed."
    except Exception as e:
        return f"Error running grep: {e}"
