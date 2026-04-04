# coder/tools/bash.py
import asyncio
import tempfile
from pygents import ContextItem, tool
from coder.shared.constants import MAX_BYTES, MAX_LINES


def _truncate_output(output: str) -> tuple[str, str | None]:
    lines = output.split("\n")
    needs_truncation = (
        len(lines) > MAX_LINES
        or len(output.encode("utf-8", errors="replace")) > MAX_BYTES
    )
    if not needs_truncation:
        return output, None
    if len(lines) > MAX_LINES:
        lines = lines[-MAX_LINES:]
    result = "\n".join(lines)
    if len(result.encode("utf-8", errors="replace")) > MAX_BYTES:
        encoded = result.encode("utf-8", errors="replace")[-MAX_BYTES:]
        result = encoded.decode("utf-8", errors="replace")
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="coder_bash_"
    )
    tmp.write(output)
    tmp.close()
    result = f"[Output truncated. Full output saved to {tmp.name}]\n\n{result}"
    return result, tmp.name


@tool()
async def tool_bash(
    command: str, timeout: int | None = None, cwd: str | None = None
):
    """Execute a bash command in the current working directory."""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            yield ContextItem(content={"role": "tool", "content": f"Command timed out after {timeout}s: {command}"})
            return
        stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""
        output = stdout_str
        if stderr_str:
            output += f"\n[stderr]\n{stderr_str}" if output else stderr_str
        if proc.returncode != 0:
            output += f"\n[Exit code: {proc.returncode}]"
        truncated, _ = _truncate_output(output)
        yield ContextItem(content={"role": "tool", "content": truncated})
    except Exception as e:
        yield ContextItem(content={"role": "tool", "content": f"Error executing command: {e}"})
