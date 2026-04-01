# Coder Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python coding agent that replicates pi-mono's architecture using pygents for orchestration and py-ai-toolkit for LLM communication.

**Architecture:** A single pygents Agent processes a turn queue. The LLM call is itself a tool (`llm_call`) that streams responses, parses tool calls, and returns Turn objects to chain execution. ContextQueue holds conversation history; ContextPool holds system prompt fragments. Compaction fires before LLM calls when token pressure is detected.

**Tech Stack:** Python 3.13, pygents 0.6.7, py-ai-toolkit 0.6.1, asyncio

**Spec:** `docs/superpowers/specs/2026-04-01-coder-agent-design.md`

---

## File Structure

```
coder/
├── __init__.py                  # Package exports
├── cli.py                       # CLI entry point, main loop, stdin reader
├── config.py                    # SessionConfig dataclass, config loading
├── session.py                   # Session lifecycle (startup, teardown)
├── agent_loop.py                # Agent creation, hook wiring
├── llm_call.py                  # The llm_call orchestration tool
├── compaction.py                # Token estimation, summarization
├── personas.py                  # Role definitions and switching
├── prompts.py                   # Slash command loading and substitution
├── resources.py                 # Project context discovery (AGENTS.md, etc.)
├── constants.py                 # Shared constants (limits, defaults)
├── tools/
│   ├── __init__.py              # Tool registration, exports
│   ├── read.py                  # read tool
│   ├── write.py                 # write tool
│   ├── edit.py                  # edit tool
│   ├── bash.py                  # bash tool
│   ├── grep.py                  # grep tool
│   ├── find.py                  # find tool
│   └── ls.py                    # ls tool
tests/
├── __init__.py
├── test_config.py
├── test_tools_read.py
├── test_tools_write.py
├── test_tools_edit.py
├── test_tools_bash.py
├── test_tools_grep.py
├── test_tools_find.py
├── test_tools_ls.py
├── test_llm_call.py
├── test_agent_loop.py
├── test_compaction.py
├── test_personas.py
├── test_prompts.py
├── test_resources.py
└── conftest.py                  # Shared fixtures (tmp dirs, registry cleanup)
main.py                          # Entry point: `python main.py`
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `coder/__init__.py`
- Create: `coder/constants.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Modify: `pyproject.toml`
- Modify: `main.py`

- [ ] **Step 1: Update pyproject.toml with dev dependencies**

```toml
[project]
name = "coder"
version = "0.1.0"
description = "A Python coding agent inspired by pi-mono"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "pygents>=0.6.7",
    "py-ai-toolkit>=0.6.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=1.3.0",
]
```

- [ ] **Step 2: Install dev dependencies**

Run: `uv sync --extra dev`
Expected: dependencies install successfully

- [ ] **Step 3: Create constants.py**

```python
# coder/constants.py

MAX_LINES = 2000
MAX_BYTES = 256 * 1024  # 256KB
GREP_MAX_MATCHES = 100
FIND_MAX_RESULTS = 1000
LS_MAX_ENTRIES = 500
GREP_MAX_LINE_LENGTH = 500
DEFAULT_HISTORY_LIMIT = 50
DEFAULT_COMPACTION_THRESHOLD = 0.8
DEFAULT_KEEP_RECENT_TOKENS = 20000
DEFAULT_TURN_TIMEOUT = 120
```

- [ ] **Step 4: Create package __init__.py**

```python
# coder/__init__.py
```

- [ ] **Step 5: Create conftest.py with shared fixtures**

```python
# tests/conftest.py
import pytest
from pygents.registry import AgentRegistry, HookRegistry, ToolRegistry


@pytest.fixture(autouse=True)
def clean_registries():
    """Clear all pygents registries before each test."""
    ToolRegistry.clear()
    AgentRegistry.clear()
    HookRegistry.clear()
    yield
    ToolRegistry.clear()
    AgentRegistry.clear()
    HookRegistry.clear()
```

```python
# tests/__init__.py
```

- [ ] **Step 6: Update main.py entry point**

```python
# main.py
import asyncio

from coder.cli import main

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 7: Run pytest to verify setup**

Run: `uv run pytest tests/ -v --co`
Expected: collects 0 tests, no import errors

- [ ] **Step 8: Commit**

```bash
git add coder/ tests/ main.py pyproject.toml
git commit -m "feat: project scaffolding with constants and test fixtures"
```

---

### Task 2: Tool — read

**Files:**
- Create: `coder/tools/__init__.py`
- Create: `coder/tools/read.py`
- Create: `tests/test_tools_read.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools_read.py
import os
import pytest
from coder.tools.read import tool_read


@pytest.mark.asyncio
async def test_read_text_file(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("line1\nline2\nline3\n")
    result = await tool_read(path=str(f))
    assert "line1" in result
    assert "line2" in result
    assert "line3" in result


@pytest.mark.asyncio
async def test_read_with_offset_and_limit(tmp_path):
    f = tmp_path / "lines.txt"
    f.write_text("\n".join(f"line{i}" for i in range(1, 11)))
    result = await tool_read(path=str(f), offset=3, limit=2)
    assert "line3" in result
    assert "line4" in result
    assert "line1" not in result
    assert "line5" not in result


@pytest.mark.asyncio
async def test_read_nonexistent_file():
    result = await tool_read(path="/tmp/nonexistent_file_xyz.txt")
    assert "error" in result.lower() or "not found" in result.lower()


@pytest.mark.asyncio
async def test_read_truncates_large_output(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * (300 * 1024))  # 300KB > 256KB limit
    result = await tool_read(path=str(f))
    assert len(result) <= 260 * 1024  # some overhead for truncation message
    assert "truncated" in result.lower()


@pytest.mark.asyncio
async def test_read_truncates_many_lines(tmp_path):
    f = tmp_path / "many_lines.txt"
    f.write_text("\n".join(f"line{i}" for i in range(3000)))  # > 2000 lines
    result = await tool_read(path=str(f))
    assert "truncated" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_read.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create tools __init__.py**

```python
# coder/tools/__init__.py
```

- [ ] **Step 4: Implement read tool**

```python
# coder/tools/read.py
import base64
import os

from pygents import tool

from coder.constants import MAX_BYTES, MAX_LINES

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
        result += f"\n\n[Output truncated. Limits: {max_lines} lines, {max_bytes // 1024}KB]"

    return result


@tool()
async def tool_read(path: str, offset: int | None = None, limit: int | None = None) -> str:
    """Read the contents of a file. Supports text files and images (jpg, png, gif, webp).
    Images are sent as base64 attachments. For text files, output is truncated to 2000
    lines or 256KB (whichever is hit first). Use offset/limit for large files."""
    try:
        if not os.path.exists(path):
            return f"Error: file not found: {path}"

        ext = os.path.splitext(path)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            return f"[Image: {path}]\nBase64: {data}"

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if offset is not None:
            start = max(0, offset - 1)  # 1-indexed
            lines = lines[start:]

        if limit is not None:
            lines = lines[:limit]

        content = "".join(lines)
        return _truncate_output(content, MAX_LINES, MAX_BYTES)
    except Exception as e:
        return f"Error reading {path}: {e}"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_read.py -v`
Expected: all 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add coder/tools/ tests/test_tools_read.py
git commit -m "feat: add read tool with truncation support"
```

---

### Task 3: Tool — write

**Files:**
- Create: `coder/tools/write.py`
- Create: `tests/test_tools_write.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools_write.py
import os
import pytest
from coder.tools.write import tool_write


@pytest.mark.asyncio
async def test_write_creates_file(tmp_path):
    f = tmp_path / "new.txt"
    result = await tool_write(path=str(f), content="hello world")
    assert os.path.exists(f)
    assert f.read_text() == "hello world"
    assert "wrote" in result.lower() or "created" in result.lower()


@pytest.mark.asyncio
async def test_write_overwrites_existing(tmp_path):
    f = tmp_path / "existing.txt"
    f.write_text("old content")
    await tool_write(path=str(f), content="new content")
    assert f.read_text() == "new content"


@pytest.mark.asyncio
async def test_write_creates_parent_dirs(tmp_path):
    f = tmp_path / "a" / "b" / "c" / "deep.txt"
    await tool_write(path=str(f), content="deep")
    assert f.read_text() == "deep"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_write.py -v`
Expected: FAIL

- [ ] **Step 3: Implement write tool**

```python
# coder/tools/write.py
import os

from pygents import tool


@tool()
async def tool_write(path: str, content: str) -> str:
    """Write content to a file. Creates the file if it doesn't exist, overwrites
    if it does. Automatically creates parent directories."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_write.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add coder/tools/write.py tests/test_tools_write.py
git commit -m "feat: add write tool with auto-dir creation"
```

---

### Task 4: Tool — edit

**Files:**
- Create: `coder/tools/edit.py`
- Create: `tests/test_tools_edit.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools_edit.py
import pytest
from coder.tools.edit import tool_edit


@pytest.mark.asyncio
async def test_edit_single_replacement(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("def hello():\n    return 'world'\n")
    result = await tool_edit(
        path=str(f),
        edits=[{"old_text": "return 'world'", "new_text": "return 'universe'"}],
    )
    assert f.read_text() == "def hello():\n    return 'universe'\n"
    assert "applied" in result.lower()


@pytest.mark.asyncio
async def test_edit_multiple_replacements(tmp_path):
    f = tmp_path / "multi.py"
    f.write_text("aaa\nbbb\nccc\n")
    result = await tool_edit(
        path=str(f),
        edits=[
            {"old_text": "aaa", "new_text": "AAA"},
            {"old_text": "ccc", "new_text": "CCC"},
        ],
    )
    assert f.read_text() == "AAA\nbbb\nCCC\n"


@pytest.mark.asyncio
async def test_edit_old_text_not_found(tmp_path):
    f = tmp_path / "miss.py"
    f.write_text("hello world\n")
    result = await tool_edit(
        path=str(f),
        edits=[{"old_text": "goodbye", "new_text": "hi"}],
    )
    assert "not found" in result.lower() or "error" in result.lower()
    assert f.read_text() == "hello world\n"  # unchanged


@pytest.mark.asyncio
async def test_edit_old_text_not_unique(tmp_path):
    f = tmp_path / "dup.py"
    f.write_text("foo\nfoo\n")
    result = await tool_edit(
        path=str(f),
        edits=[{"old_text": "foo", "new_text": "bar"}],
    )
    assert "unique" in result.lower() or "multiple" in result.lower() or "error" in result.lower()
    assert f.read_text() == "foo\nfoo\n"  # unchanged


@pytest.mark.asyncio
async def test_edit_nonexistent_file():
    result = await tool_edit(
        path="/tmp/nonexistent_xyz.py",
        edits=[{"old_text": "a", "new_text": "b"}],
    )
    assert "error" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_edit.py -v`
Expected: FAIL

- [ ] **Step 3: Implement edit tool**

```python
# coder/tools/edit.py
import os
from typing import TypedDict

from pygents import tool


class EditEntry(TypedDict):
    old_text: str
    new_text: str


@tool()
async def tool_edit(path: str, edits: list[EditEntry]) -> str:
    """Edit a single file using exact text replacement. Every edit's old_text must
    match a unique, non-overlapping region of the original file. All old_text values
    are matched against the original file, not after earlier edits are applied."""
    try:
        if not os.path.exists(path):
            return f"Error: file not found: {path}"

        with open(path, "r", encoding="utf-8") as f:
            original = f.read()

        # Validate all edits against original content before applying any
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

        # Check for overlaps
        replacements.sort(key=lambda r: r[0])
        for j in range(len(replacements) - 1):
            if replacements[j][1] > replacements[j + 1][0]:
                return f"Error: edits overlap in {path}"

        # Apply replacements in reverse order to preserve positions
        result = original
        for start, end, new_text in reversed(replacements):
            result = result[:start] + new_text + result[end:]

        with open(path, "w", encoding="utf-8") as f:
            f.write(result)

        return f"Applied {len(edits)} edit(s) to {path}"
    except Exception as e:
        return f"Error editing {path}: {e}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_edit.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add coder/tools/edit.py tests/test_tools_edit.py
git commit -m "feat: add edit tool with overlap and uniqueness validation"
```

---

### Task 5: Tool — bash

**Files:**
- Create: `coder/tools/bash.py`
- Create: `tests/test_tools_bash.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools_bash.py
import pytest
from coder.tools.bash import tool_bash


@pytest.mark.asyncio
async def test_bash_simple_command():
    result = await tool_bash(command="echo hello")
    assert "hello" in result


@pytest.mark.asyncio
async def test_bash_stderr():
    result = await tool_bash(command="echo err >&2")
    assert "err" in result


@pytest.mark.asyncio
async def test_bash_exit_code():
    result = await tool_bash(command="exit 1")
    assert "exit code" in result.lower() or "1" in result


@pytest.mark.asyncio
async def test_bash_timeout():
    result = await tool_bash(command="sleep 10", timeout=1)
    assert "timeout" in result.lower() or "timed out" in result.lower()


@pytest.mark.asyncio
async def test_bash_cwd(tmp_path):
    result = await tool_bash(command=f"pwd", cwd=str(tmp_path))
    assert str(tmp_path) in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_bash.py -v`
Expected: FAIL

- [ ] **Step 3: Implement bash tool**

```python
# coder/tools/bash.py
import asyncio
import tempfile

from pygents import tool

from coder.constants import MAX_BYTES, MAX_LINES


def _truncate_output(output: str) -> tuple[str, str | None]:
    """Truncate output and return (truncated_output, temp_file_path_or_none)."""
    lines = output.split("\n")
    needs_truncation = len(lines) > MAX_LINES or len(output.encode("utf-8", errors="replace")) > MAX_BYTES

    if not needs_truncation:
        return output, None

    # Keep last MAX_LINES lines
    if len(lines) > MAX_LINES:
        lines = lines[-MAX_LINES:]

    result = "\n".join(lines)

    if len(result.encode("utf-8", errors="replace")) > MAX_BYTES:
        encoded = result.encode("utf-8", errors="replace")[-MAX_BYTES:]
        result = encoded.decode("utf-8", errors="replace")

    # Save full output to temp file
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, prefix="coder_bash_")
    tmp.write(output)
    tmp.close()

    result = f"[Output truncated. Full output saved to {tmp.name}]\n\n{result}"
    return result, tmp.name


@tool()
async def tool_bash(command: str, timeout: int | None = None, cwd: str | None = None) -> str:
    """Execute a bash command in the current working directory. Returns stdout and stderr.
    Output is truncated to last 2000 lines or 256KB. If truncated, full output is saved
    to a temp file."""
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
            return f"Command timed out after {timeout}s: {command}"

        stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

        output = stdout_str
        if stderr_str:
            output += f"\n[stderr]\n{stderr_str}" if output else stderr_str

        if proc.returncode != 0:
            output += f"\n[Exit code: {proc.returncode}]"

        truncated, _ = _truncate_output(output)
        return truncated
    except Exception as e:
        return f"Error executing command: {e}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_bash.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add coder/tools/bash.py tests/test_tools_bash.py
git commit -m "feat: add bash tool with timeout and truncation"
```

---

### Task 6: Tool — grep

**Files:**
- Create: `coder/tools/grep.py`
- Create: `tests/test_tools_grep.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools_grep.py
import os
import pytest
from coder.tools.grep import tool_grep


@pytest.mark.asyncio
async def test_grep_finds_pattern(tmp_path):
    (tmp_path / "a.py").write_text("def hello():\n    pass\n")
    (tmp_path / "b.py").write_text("def world():\n    pass\n")
    result = await tool_grep(pattern="hello", path=str(tmp_path))
    assert "a.py" in result
    assert "hello" in result


@pytest.mark.asyncio
async def test_grep_respects_glob_filter(tmp_path):
    (tmp_path / "code.py").write_text("match here\n")
    (tmp_path / "notes.txt").write_text("match here too\n")
    result = await tool_grep(pattern="match", path=str(tmp_path), glob="*.py")
    assert "code.py" in result
    assert "notes.txt" not in result


@pytest.mark.asyncio
async def test_grep_case_insensitive(tmp_path):
    (tmp_path / "f.txt").write_text("Hello World\n")
    result = await tool_grep(pattern="hello", path=str(tmp_path), ignore_case=True)
    assert "Hello" in result


@pytest.mark.asyncio
async def test_grep_no_matches(tmp_path):
    (tmp_path / "f.txt").write_text("nothing here\n")
    result = await tool_grep(pattern="zzzzz", path=str(tmp_path))
    assert "no matches" in result.lower() or result.strip() == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_grep.py -v`
Expected: FAIL

- [ ] **Step 3: Implement grep tool**

```python
# coder/tools/grep.py
import asyncio

from pygents import tool

from coder.constants import GREP_MAX_LINE_LENGTH, GREP_MAX_MATCHES, MAX_BYTES


@tool()
async def tool_grep(
    pattern: str,
    path: str | None = None,
    glob: str | None = None,
    ignore_case: bool = False,
    literal: bool = False,
    context: int | None = None,
    limit: int | None = None,
) -> str:
    """Search file contents for a pattern. Returns matching lines with file paths
    and line numbers. Respects .gitignore. Truncated to 100 matches or 256KB."""
    args = ["rg", "--no-heading", "--line-number", "--color=never"]

    if ignore_case:
        args.append("-i")
    if literal:
        args.append("-F")
    if context is not None:
        args.extend(["-C", str(context)])
    if glob is not None:
        args.extend(["--glob", glob])

    max_matches = limit if limit is not None else GREP_MAX_MATCHES
    args.extend(["-m", str(max_matches)])
    args.append(pattern)

    if path:
        args.append(path)

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace")

        if not output.strip():
            return "No matches found."

        # Truncate long lines
        lines = output.split("\n")
        lines = [
            line[:GREP_MAX_LINE_LENGTH] + "..." if len(line) > GREP_MAX_LINE_LENGTH else line
            for line in lines
        ]
        output = "\n".join(lines)

        # Truncate total size
        if len(output.encode("utf-8", errors="replace")) > MAX_BYTES:
            encoded = output.encode("utf-8", errors="replace")[:MAX_BYTES]
            output = encoded.decode("utf-8", errors="replace")
            output += f"\n\n[Output truncated at {MAX_BYTES // 1024}KB]"

        return output
    except FileNotFoundError:
        return "Error: 'rg' (ripgrep) is not installed. Install it to use grep."
    except Exception as e:
        return f"Error running grep: {e}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_grep.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add coder/tools/grep.py tests/test_tools_grep.py
git commit -m "feat: add grep tool using ripgrep"
```

---

### Task 7: Tool — find

**Files:**
- Create: `coder/tools/find.py`
- Create: `tests/test_tools_find.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools_find.py
import os
import pytest
from coder.tools.find import tool_find


@pytest.mark.asyncio
async def test_find_by_glob(tmp_path):
    (tmp_path / "foo.py").write_text("")
    (tmp_path / "bar.py").write_text("")
    (tmp_path / "baz.txt").write_text("")
    result = await tool_find(pattern="*.py", path=str(tmp_path))
    assert "foo.py" in result
    assert "bar.py" in result
    assert "baz.txt" not in result


@pytest.mark.asyncio
async def test_find_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.py").write_text("")
    result = await tool_find(pattern="**/*.py", path=str(tmp_path))
    assert "deep.py" in result


@pytest.mark.asyncio
async def test_find_no_matches(tmp_path):
    (tmp_path / "a.txt").write_text("")
    result = await tool_find(pattern="*.xyz", path=str(tmp_path))
    assert "no matches" in result.lower() or result.strip() == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_find.py -v`
Expected: FAIL

- [ ] **Step 3: Implement find tool**

```python
# coder/tools/find.py
import asyncio

from pygents import tool

from coder.constants import FIND_MAX_RESULTS, MAX_BYTES


@tool()
async def tool_find(
    pattern: str,
    path: str | None = None,
    limit: int | None = None,
) -> str:
    """Search for files by glob pattern. Returns matching file paths relative to the
    search directory. Respects .gitignore. Truncated to 1000 results or 256KB."""
    args = ["rg", "--files", "--glob", pattern, "--color=never"]

    if path:
        args.append(path)

    max_results = limit if limit is not None else FIND_MAX_RESULTS

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace")

        if not output.strip():
            return "No matches found."

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
        return "Error: 'rg' (ripgrep) is not installed. Install it to use find."
    except Exception as e:
        return f"Error running find: {e}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_find.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add coder/tools/find.py tests/test_tools_find.py
git commit -m "feat: add find tool using ripgrep"
```

---

### Task 8: Tool — ls

**Files:**
- Create: `coder/tools/ls.py`
- Create: `tests/test_tools_ls.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools_ls.py
import os
import pytest
from coder.tools.ls import tool_ls


@pytest.mark.asyncio
async def test_ls_lists_files(tmp_path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "b.py").write_text("")
    result = await tool_ls(path=str(tmp_path))
    assert "a.txt" in result
    assert "b.py" in result


@pytest.mark.asyncio
async def test_ls_marks_directories(tmp_path):
    (tmp_path / "subdir").mkdir()
    (tmp_path / "file.txt").write_text("")
    result = await tool_ls(path=str(tmp_path))
    assert "subdir/" in result
    assert "file.txt" in result


@pytest.mark.asyncio
async def test_ls_sorted_alphabetically(tmp_path):
    (tmp_path / "zebra.txt").write_text("")
    (tmp_path / "alpha.txt").write_text("")
    result = await tool_ls(path=str(tmp_path))
    alpha_pos = result.index("alpha.txt")
    zebra_pos = result.index("zebra.txt")
    assert alpha_pos < zebra_pos


@pytest.mark.asyncio
async def test_ls_includes_dotfiles(tmp_path):
    (tmp_path / ".hidden").write_text("")
    (tmp_path / "visible.txt").write_text("")
    result = await tool_ls(path=str(tmp_path))
    assert ".hidden" in result


@pytest.mark.asyncio
async def test_ls_nonexistent_path():
    result = await tool_ls(path="/tmp/nonexistent_dir_xyz")
    assert "error" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_ls.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ls tool**

```python
# coder/tools/ls.py
import os

from pygents import tool

from coder.constants import LS_MAX_ENTRIES, MAX_BYTES


@tool()
async def tool_ls(path: str | None = None, limit: int | None = None) -> str:
    """List directory contents. Returns entries sorted alphabetically, with '/'
    suffix for directories. Includes dotfiles. Truncated to 500 entries or 256KB."""
    target = path if path else os.getcwd()
    max_entries = limit if limit is not None else LS_MAX_ENTRIES

    try:
        if not os.path.isdir(target):
            return f"Error: not a directory: {target}"

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

        return result
    except Exception as e:
        return f"Error listing {target}: {e}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_ls.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add coder/tools/ls.py tests/test_tools_ls.py
git commit -m "feat: add ls tool with sorted output and dir markers"
```

---

### Task 9: Config and Resource Discovery

**Files:**
- Create: `coder/config.py`
- Create: `coder/resources.py`
- Create: `tests/test_config.py`
- Create: `tests/test_resources.py`

- [ ] **Step 1: Write the failing config tests**

```python
# tests/test_config.py
import os
import pytest
from coder.config import SessionConfig, load_config


def test_config_defaults():
    config = SessionConfig()
    assert config.history_limit == 50
    assert config.compaction_threshold == 0.8
    assert config.keep_recent_tokens == 20000


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-4-5")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    config = SessionConfig.from_env()
    assert config.model == "claude-sonnet-4-5"
    assert config.api_key == "test-key"


def test_load_config_from_yaml(tmp_path):
    config_file = tmp_path / ".coder" / "config.yaml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("history_limit: 100\ncompaction_threshold: 0.9\n")
    config = load_config(cwd=str(tmp_path))
    assert config.history_limit == 100
    assert config.compaction_threshold == 0.9


def test_load_config_no_file(tmp_path):
    config = load_config(cwd=str(tmp_path))
    assert config.history_limit == 50  # default
```

- [ ] **Step 2: Write the failing resource tests**

```python
# tests/test_resources.py
import os
import pytest
from coder.resources import discover_project_context, load_system_prompt_override, load_append_prompt


def test_discover_agents_md(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Agent rules\nBe helpful.\n")
    result = discover_project_context(cwd=str(tmp_path))
    assert "Be helpful" in result


def test_discover_claude_md(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# Claude config\nUse TDD.\n")
    result = discover_project_context(cwd=str(tmp_path))
    assert "Use TDD" in result


def test_discover_walks_upward(tmp_path):
    (tmp_path / "AGENTS.md").write_text("root rules")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    result = discover_project_context(cwd=str(sub))
    assert "root rules" in result


def test_discover_no_files(tmp_path):
    result = discover_project_context(cwd=str(tmp_path))
    assert result == ""


def test_load_system_override(tmp_path):
    coder_dir = tmp_path / ".coder"
    coder_dir.mkdir()
    (coder_dir / "SYSTEM.md").write_text("Custom system prompt")
    result = load_system_prompt_override(cwd=str(tmp_path))
    assert result == "Custom system prompt"


def test_load_system_override_missing(tmp_path):
    result = load_system_prompt_override(cwd=str(tmp_path))
    assert result is None


def test_load_append_prompt(tmp_path):
    coder_dir = tmp_path / ".coder"
    coder_dir.mkdir()
    (coder_dir / "APPEND_SYSTEM.md").write_text("Extra instructions")
    result = load_append_prompt(cwd=str(tmp_path))
    assert result == "Extra instructions"


def test_load_append_prompt_missing(tmp_path):
    result = load_append_prompt(cwd=str(tmp_path))
    assert result is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py tests/test_resources.py -v`
Expected: FAIL

- [ ] **Step 4: Implement config.py**

```python
# coder/config.py
import os
from dataclasses import dataclass, field

import yaml

from coder.constants import (
    DEFAULT_COMPACTION_THRESHOLD,
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_KEEP_RECENT_TOKENS,
)


@dataclass
class SessionConfig:
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    history_limit: int = DEFAULT_HISTORY_LIMIT
    compaction_threshold: float = DEFAULT_COMPACTION_THRESHOLD
    keep_recent_tokens: int = DEFAULT_KEEP_RECENT_TOKENS
    cwd: str = field(default_factory=os.getcwd)

    @classmethod
    def from_env(cls) -> "SessionConfig":
        return cls(
            model=os.environ.get("LLM_MODEL", ""),
            api_key=os.environ.get("LLM_API_KEY", ""),
            base_url=os.environ.get("LLM_BASE_URL", ""),
        )


def load_config(cwd: str | None = None) -> SessionConfig:
    """Load config from env vars, then overlay with .coder/config.yaml if present."""
    config = SessionConfig.from_env()
    config.cwd = cwd or os.getcwd()

    config_path = os.path.join(config.cwd, ".coder", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}
        if "history_limit" in data:
            config.history_limit = data["history_limit"]
        if "compaction_threshold" in data:
            config.compaction_threshold = data["compaction_threshold"]
        if "keep_recent_tokens" in data:
            config.keep_recent_tokens = data["keep_recent_tokens"]
        if "model" in data:
            config.model = data["model"]
        if "api_key" in data:
            config.api_key = data["api_key"]
        if "base_url" in data:
            config.base_url = data["base_url"]

    return config
```

- [ ] **Step 5: Add pyyaml dependency**

Run: `uv add pyyaml`

Note: pyyaml is already installed as a transitive dependency of py-ai-toolkit, but adding it explicitly ensures it's available.

- [ ] **Step 6: Implement resources.py**

```python
# coder/resources.py
import os

CONTEXT_FILES = ["AGENTS.md", "CLAUDE.md"]


def discover_project_context(cwd: str) -> str:
    """Walk from cwd upward, collecting AGENTS.md and CLAUDE.md content.
    Also checks ~/.coder/agent/ for global config."""
    fragments: list[str] = []
    seen_paths: set[str] = set()

    current = os.path.abspath(cwd)
    while True:
        for name in CONTEXT_FILES:
            path = os.path.join(current, name)
            if os.path.isfile(path) and path not in seen_paths:
                seen_paths.add(path)
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().strip()
                if content:
                    fragments.append(f"# {path}\n{content}")

        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    # Check global config
    global_dir = os.path.expanduser("~/.coder/agent")
    if os.path.isdir(global_dir):
        for name in CONTEXT_FILES:
            path = os.path.join(global_dir, name)
            if os.path.isfile(path) and path not in seen_paths:
                seen_paths.add(path)
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().strip()
                if content:
                    fragments.append(f"# {path}\n{content}")

    return "\n\n".join(fragments)


def load_system_prompt_override(cwd: str) -> str | None:
    """Load .coder/SYSTEM.md if it exists. Replaces the entire default base prompt."""
    path = os.path.join(cwd, ".coder", "SYSTEM.md")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None


def load_append_prompt(cwd: str) -> str | None:
    """Load .coder/APPEND_SYSTEM.md if it exists. Appended to the system prompt."""
    path = os.path.join(cwd, ".coder", "APPEND_SYSTEM.md")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py tests/test_resources.py -v`
Expected: all tests PASS

- [ ] **Step 8: Commit**

```bash
git add coder/config.py coder/resources.py tests/test_config.py tests/test_resources.py
git commit -m "feat: add config loading and project context discovery"
```

---

### Task 10: Slash Command Loading

**Files:**
- Create: `coder/prompts.py`
- Create: `tests/test_prompts.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_prompts.py
import os
import pytest
from coder.prompts import load_slash_command, list_slash_commands, is_slash_command


def test_is_slash_command():
    assert is_slash_command("/plan fix the bug")
    assert is_slash_command("/pr")
    assert not is_slash_command("hello")
    assert not is_slash_command("")


def test_load_slash_command(tmp_path):
    prompts_dir = tmp_path / ".coder" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "plan.md").write_text("Create a plan for: $ARGUMENTS")
    result = load_slash_command("/plan fix the auth bug", cwd=str(tmp_path))
    assert result == "Create a plan for: fix the auth bug"


def test_load_slash_command_dollar_at(tmp_path):
    prompts_dir = tmp_path / ".coder" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "pr.md").write_text("Review PR $@")
    result = load_slash_command("/pr 123", cwd=str(tmp_path))
    assert result == "Review PR 123"


def test_load_slash_command_no_args(tmp_path):
    prompts_dir = tmp_path / ".coder" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "cl.md").write_text("Run changelog audit")
    result = load_slash_command("/cl", cwd=str(tmp_path))
    assert result == "Run changelog audit"


def test_load_slash_command_not_found(tmp_path):
    result = load_slash_command("/missing", cwd=str(tmp_path))
    assert result is None


def test_list_slash_commands(tmp_path):
    prompts_dir = tmp_path / ".coder" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "plan.md").write_text("")
    (prompts_dir / "pr.md").write_text("")
    (prompts_dir / "not_md.txt").write_text("")
    commands = list_slash_commands(cwd=str(tmp_path))
    assert "plan" in commands
    assert "pr" in commands
    assert "not_md" not in commands
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: FAIL

- [ ] **Step 3: Implement prompts.py**

```python
# coder/prompts.py
import os


def is_slash_command(text: str) -> bool:
    """Check if text starts with a slash command."""
    return bool(text) and text.startswith("/") and len(text) > 1


def load_slash_command(text: str, cwd: str) -> str | None:
    """Parse a slash command, load the template, substitute arguments, and return the expanded prompt.
    Returns None if the command template is not found."""
    parts = text.split(None, 1)
    command = parts[0][1:]  # strip leading /
    arguments = parts[1] if len(parts) > 1 else ""

    prompts_dir = os.path.join(cwd, ".coder", "prompts")
    template_path = os.path.join(prompts_dir, f"{command}.md")

    if not os.path.isfile(template_path):
        return None

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    result = template.replace("$ARGUMENTS", arguments)
    result = result.replace("$@", arguments)
    return result


def list_slash_commands(cwd: str) -> list[str]:
    """List available slash commands by scanning .coder/prompts/ for .md files."""
    prompts_dir = os.path.join(cwd, ".coder", "prompts")
    if not os.path.isdir(prompts_dir):
        return []

    commands = []
    for name in sorted(os.listdir(prompts_dir)):
        if name.endswith(".md"):
            commands.append(name[:-3])
    return commands
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add coder/prompts.py tests/test_prompts.py
git commit -m "feat: add slash command loading with argument substitution"
```

---

### Task 11: Compaction

**Files:**
- Create: `coder/compaction.py`
- Create: `tests/test_compaction.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_compaction.py
import pytest
from pygents import ContextItem, ContextPool, ContextQueue

from coder.compaction import (
    estimate_tokens,
    should_compact,
    split_messages,
    SUMMARIZATION_PROMPT,
    SUMMARIZATION_SYSTEM_PROMPT,
    UPDATE_SUMMARIZATION_PROMPT,
)


def test_estimate_tokens():
    items = [
        ContextItem(content={"role": "user", "content": "hello world"}),
    ]
    tokens = estimate_tokens(items)
    assert tokens > 0
    assert tokens == len(str({"role": "user", "content": "hello world"})) // 4


def test_should_compact_under_threshold():
    items = [ContextItem(content={"role": "user", "content": "short"})]
    assert not should_compact(items, threshold=0.8, max_context_tokens=100000)


def test_should_compact_over_threshold():
    big_content = "x" * 400000  # ~100k tokens
    items = [ContextItem(content={"role": "user", "content": big_content})]
    assert should_compact(items, threshold=0.8, max_context_tokens=50000)


def test_split_messages():
    items = [ContextItem(content={"role": "user", "content": f"msg{i}"}) for i in range(10)]
    old, recent = split_messages(items, keep_recent_tokens=50)
    assert len(old) + len(recent) == 10
    assert len(recent) > 0
    assert len(old) > 0


def test_summarization_prompts_exist():
    assert "Goal" in SUMMARIZATION_PROMPT
    assert "Progress" in SUMMARIZATION_PROMPT
    assert "context summarization" in SUMMARIZATION_SYSTEM_PROMPT.lower()
    assert "PRESERVE" in UPDATE_SUMMARIZATION_PROMPT
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_compaction.py -v`
Expected: FAIL

- [ ] **Step 3: Implement compaction.py**

```python
# coder/compaction.py
from pygents import ContextItem

SUMMARIZATION_SYSTEM_PROMPT = """You are a context summarization assistant. Your task is to read a conversation between a user and an AI coding assistant, then produce a structured summary following the exact format specified.

Do NOT continue the conversation. Do NOT respond to any questions in the conversation. ONLY output the structured summary."""

SUMMARIZATION_PROMPT = """The messages above are a conversation to summarize. Create a structured context checkpoint summary that another LLM will use to continue the work.

Use this EXACT format:

## Goal
[What is the user trying to accomplish? Can be multiple items if the session covers different tasks.]

## Constraints & Preferences
- [Any constraints, preferences, or requirements mentioned by user]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Completed tasks/changes]

### In Progress
- [ ] [Current work]

### Blocked
- [Issues preventing progress, if any]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [Ordered list of what should happen next]

## Critical Context
- [Any data, examples, or references needed to continue]
- [Or "(none)" if not applicable]

Keep each section concise. Preserve exact file paths, function names, and error messages."""

UPDATE_SUMMARIZATION_PROMPT = """The messages above are NEW conversation messages to incorporate into the existing summary provided in <previous-summary> tags.

Update the existing structured summary with new information. RULES:
- PRESERVE all existing information from the previous summary
- ADD new progress, decisions, and context from the new messages
- UPDATE the Progress section: move items from "In Progress" to "Done" when completed
- UPDATE "Next Steps" based on what was accomplished
- PRESERVE exact file paths, function names, and error messages
- If something is no longer relevant, you may remove it

Use this EXACT format:

## Goal
[Preserve existing goals, add new ones if the task expanded]

## Constraints & Preferences
- [Preserve existing, add new ones discovered]

## Progress
### Done
- [x] [Include previously done items AND newly completed items]

### In Progress
- [ ] [Current work - update based on progress]

### Blocked
- [Current blockers - remove if resolved]

## Key Decisions
- **[Decision]**: [Brief rationale] (preserve all previous, add new)

## Next Steps
1. [Update based on current state]

## Critical Context
- [Preserve important context, add new if needed]

Keep each section concise. Preserve exact file paths, function names, and error messages."""

TURN_PREFIX_SUMMARIZATION_PROMPT = """This is the PREFIX of a turn that was too large to keep. The SUFFIX (recent work) is retained.

Summarize the prefix to provide context for the retained suffix:

## Original Request
[What did the user ask for in this turn?]

## Early Progress
- [Key decisions and work done in the prefix]

## Context for Suffix
- [Information needed to understand the retained recent work]

Be concise. Focus on what's needed to understand the kept suffix."""

BRANCH_SUMMARY_PROMPT = """Create a structured summary of this conversation branch for context when returning later.

Use this EXACT format:

## Goal
[What was the user trying to accomplish in this branch?]

## Constraints & Preferences
- [Any constraints, preferences, or requirements mentioned]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Completed tasks/changes]

### In Progress
- [ ] [Work that was started but not finished]

### Blocked
- [Issues preventing progress, if any]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [What should happen next to continue this work]

Keep each section concise. Preserve exact file paths, function names, and error messages."""

BRANCH_SUMMARY_PREAMBLE = """The user explored a different conversation branch before returning here.
Summary of that exploration:
"""


def estimate_tokens(items: list[ContextItem]) -> int:
    """Estimate token count using len(str(content)) // 4 heuristic."""
    total = 0
    for item in items:
        total += len(str(item.content)) // 4
    return total


def should_compact(
    items: list[ContextItem],
    threshold: float,
    max_context_tokens: int,
) -> bool:
    """Return True if estimated tokens exceed threshold * max_context_tokens."""
    tokens = estimate_tokens(items)
    return tokens > threshold * max_context_tokens


def split_messages(
    items: list[ContextItem],
    keep_recent_tokens: int,
) -> tuple[list[ContextItem], list[ContextItem]]:
    """Walk backward through items, keeping recent items until keep_recent_tokens
    worth of tokens are preserved. Returns (old_messages, recent_messages)."""
    recent_tokens = 0
    split_index = len(items)

    for i in range(len(items) - 1, -1, -1):
        item_tokens = len(str(items[i].content)) // 4
        if recent_tokens + item_tokens > keep_recent_tokens:
            split_index = i + 1
            break
        recent_tokens += item_tokens
    else:
        split_index = 0

    return list(items[:split_index]), list(items[split_index:])


async def run_compaction(
    toolkit,
    items: list[ContextItem],
    existing_summary: str | None,
    keep_recent_tokens: int,
) -> tuple[str, list[ContextItem]]:
    """Run compaction: summarize old messages, return (summary, recent_messages).

    Args:
        toolkit: PyAIToolkit instance
        items: all context items
        existing_summary: previous compaction summary, or None
        keep_recent_tokens: how many tokens of recent messages to preserve

    Returns:
        (summary_text, recent_messages_to_keep)
    """
    old_messages, recent_messages = split_messages(items, keep_recent_tokens)

    if not old_messages:
        return existing_summary or "", recent_messages

    # Format old messages for summarization
    conversation = "\n".join(
        f"[{item.content.get('role', 'unknown')}]: {item.content.get('content', str(item.content))}"
        for item in old_messages
        if isinstance(item.content, dict)
    )

    if existing_summary:
        prompt_template = (
            "<previous-summary>\n{{ previous_summary }}\n</previous-summary>\n\n"
            "{{ conversation }}\n\n"
            "{{ update_prompt }}"
        )
        response = await toolkit.chat(
            template=prompt_template,
            previous_summary=existing_summary,
            conversation=conversation,
            update_prompt=UPDATE_SUMMARIZATION_PROMPT,
            system=SUMMARIZATION_SYSTEM_PROMPT,
        )
    else:
        prompt_template = "{{ conversation }}\n\n{{ summarize_prompt }}"
        response = await toolkit.chat(
            template=prompt_template,
            conversation=conversation,
            summarize_prompt=SUMMARIZATION_PROMPT,
            system=SUMMARIZATION_SYSTEM_PROMPT,
        )

    return response.content, recent_messages
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_compaction.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add coder/compaction.py tests/test_compaction.py
git commit -m "feat: add compaction with summarization prompts from pi-mono"
```

---

### Task 12: Personas (Role Switching)

**Files:**
- Create: `coder/personas.py`
- Create: `tests/test_personas.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_personas.py
import pytest
from coder.personas import PERSONAS, get_persona, get_allowed_tools


def test_all_personas_exist():
    assert "scout" in PERSONAS
    assert "planner" in PERSONAS
    assert "worker" in PERSONAS
    assert "reviewer" in PERSONAS


def test_get_persona():
    persona = get_persona("scout")
    assert persona.name == "scout"
    assert persona.system_prompt
    assert "scout" in persona.system_prompt.lower() or "investigate" in persona.system_prompt.lower()


def test_get_persona_not_found():
    with pytest.raises(KeyError):
        get_persona("nonexistent")


def test_scout_tools():
    tools = get_allowed_tools("scout")
    assert "tool_read" in tools
    assert "tool_bash" in tools
    assert "tool_grep" in tools
    assert "tool_find" in tools
    assert "tool_ls" in tools
    assert "tool_write" not in tools
    assert "tool_edit" not in tools


def test_worker_tools():
    tools = get_allowed_tools("worker")
    assert "tool_read" in tools
    assert "tool_write" in tools
    assert "tool_edit" in tools
    assert "tool_bash" in tools
    assert "tool_grep" in tools
    assert "tool_find" in tools
    assert "tool_ls" in tools


def test_reviewer_no_write_tools():
    tools = get_allowed_tools("reviewer")
    assert "tool_write" not in tools
    assert "tool_edit" not in tools
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_personas.py -v`
Expected: FAIL

- [ ] **Step 3: Implement personas.py**

```python
# coder/personas.py
from dataclasses import dataclass


@dataclass
class Persona:
    name: str
    system_prompt: str
    model_hint: str
    allowed_tools: frozenset[str]


READ_ONLY_TOOLS = frozenset({"tool_read", "tool_bash", "tool_grep", "tool_find", "tool_ls"})
ALL_TOOLS = frozenset({"tool_read", "tool_write", "tool_edit", "tool_bash", "tool_grep", "tool_find", "tool_ls"})

SCOUT_PROMPT = """You are a scout. Quickly investigate a codebase and return structured findings that another agent can use without re-reading everything.

Your output will be passed to an agent who has NOT seen the files you explored.

Thoroughness (infer from task, default medium):
- Quick: Targeted lookups, key files only
- Medium: Follow imports, read critical sections
- Thorough: Trace all dependencies, check tests/types

Strategy:
1. grep/find to locate relevant code
2. Read key sections (not entire files)
3. Identify types, interfaces, key functions
4. Note dependencies between files

Output format:

## Files Retrieved
List with exact line ranges:
1. `path/to/file` (lines 10-50) - Description of what's here
2. `path/to/other` (lines 100-150) - Description
3. ...

## Key Code
Critical types, interfaces, or functions (actual code from the files).

## Architecture
Brief explanation of how the pieces connect.

## Start Here
Which file to look at first and why."""

PLANNER_PROMPT = """You are a planning specialist. You receive context (from a scout) and requirements, then produce a clear implementation plan.

You must NOT make any changes. Only read, analyze, and plan.

Output format:

## Goal
One sentence summary of what needs to be done.

## Plan
Numbered steps, each small and actionable:
1. Step one - specific file/function to modify
2. Step two - what to add/change

## Files to Modify
- `path/to/file` - what changes

## New Files (if any)
- `path/to/new` - purpose

## Risks
Anything to watch out for.

Keep the plan concrete. The worker agent will execute it verbatim."""

WORKER_PROMPT = """You are a worker agent with full capabilities. You operate in an isolated context window to handle delegated tasks without polluting the main conversation.

Work autonomously to complete the assigned task. Use all available tools as needed.

Output format when finished:

## Completed
What was done.

## Files Changed
- `path/to/file` - what changed

## Notes (if any)
Anything the main agent should know.

If handing off to another agent (e.g. reviewer), include:
- Exact file paths changed
- Key functions/types touched (short list)"""

REVIEWER_PROMPT = """You are a senior code reviewer. Analyze code for quality, security, and maintainability.

Bash is for read-only commands only: git diff, git log, git show. Do NOT modify files or run builds.

Strategy:
1. Run git diff to see recent changes (if applicable)
2. Read the modified files
3. Check for bugs, security issues, code smells

Output format:

## Files Reviewed
- `path/to/file` (lines X-Y)

## Critical (must fix)
- `file:42` - Issue description

## Warnings (should fix)
- `file:100` - Issue description

## Suggestions (consider)
- `file:150` - Improvement idea

## Summary
Overall assessment in 2-3 sentences.

Be specific with file paths and line numbers."""

PERSONAS: dict[str, Persona] = {
    "scout": Persona(
        name="scout",
        system_prompt=SCOUT_PROMPT,
        model_hint="haiku",
        allowed_tools=READ_ONLY_TOOLS,
    ),
    "planner": Persona(
        name="planner",
        system_prompt=PLANNER_PROMPT,
        model_hint="sonnet",
        allowed_tools=READ_ONLY_TOOLS,
    ),
    "worker": Persona(
        name="worker",
        system_prompt=WORKER_PROMPT,
        model_hint="sonnet",
        allowed_tools=ALL_TOOLS,
    ),
    "reviewer": Persona(
        name="reviewer",
        system_prompt=REVIEWER_PROMPT,
        model_hint="sonnet",
        allowed_tools=READ_ONLY_TOOLS,
    ),
}


def get_persona(name: str) -> Persona:
    """Get a persona by name. Raises KeyError if not found."""
    return PERSONAS[name]


def get_allowed_tools(name: str) -> frozenset[str]:
    """Get the allowed tool names for a persona."""
    return PERSONAS[name].allowed_tools
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_personas.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add coder/personas.py tests/test_personas.py
git commit -m "feat: add persona definitions with pi-mono prompts"
```

---

### Task 13: llm_call Tool

**Files:**
- Create: `coder/llm_call.py`
- Create: `tests/test_llm_call.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_llm_call.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pygents import ContextItem, ContextPool, ContextQueue

from coder.llm_call import build_system_prompt, build_messages, tool_llm_call


def test_build_system_prompt_basic():
    pool = ContextPool()
    # Must use sync operations for test setup — bypass hooks
    pool._items["base-prompt"] = ContextItem(
        id="base-prompt",
        description="Base system prompt",
        content="You are a coding assistant.\n\nGuidelines:\n{guidelines}",
    )
    prompt = build_system_prompt(pool, allowed_tools=None, tools_list="- read\n- bash")
    assert "coding assistant" in prompt
    assert "read" in prompt


def test_build_system_prompt_with_role():
    pool = ContextPool()
    pool._items["base-prompt"] = ContextItem(
        id="base-prompt",
        description="Base",
        content="Base prompt.\n\nGuidelines:\n{guidelines}",
    )
    pool._items["active-role"] = ContextItem(
        id="active-role",
        description="Active role",
        content="You are a scout.",
    )
    prompt = build_system_prompt(pool, allowed_tools=None, tools_list="- read")
    assert "scout" in prompt


def test_build_messages():
    cq = ContextQueue(limit=10)
    # Bypass async append for test setup
    cq._items.append(ContextItem(content={"role": "user", "content": "hello"}))
    cq._items.append(ContextItem(content={"role": "assistant", "content": "hi there"}))
    messages = build_messages(cq)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_build_messages_with_compaction_summary():
    cq = ContextQueue(limit=10)
    cq._items.append(ContextItem(content={"role": "user", "content": "hello"}))
    pool = ContextPool()
    pool._items["compaction-summary"] = ContextItem(
        id="compaction-summary",
        description="Summary",
        content="Previous work summary here.",
    )
    messages = build_messages(cq, compaction_summary="Previous work summary here.")
    assert len(messages) == 2
    assert "Previous work" in messages[0]["content"]
    assert messages[0]["role"] == "system"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_llm_call.py -v`
Expected: FAIL

- [ ] **Step 3: Implement llm_call.py**

```python
# coder/llm_call.py
import json
import sys
from typing import Any

from pygents import ContextItem, ContextPool, ContextQueue, Turn, tool
from pygents.registry import ToolRegistry

# Tool names that are exposed to the LLM (not llm_call itself)
LLM_VISIBLE_TOOLS = {"tool_read", "tool_write", "tool_edit", "tool_bash", "tool_grep", "tool_find", "tool_ls"}

# Default guidelines
GUIDELINE_BASH_ONLY = "Use bash for file operations like ls, rg, find"
GUIDELINE_PREFER_TOOLS = "Prefer grep/find/ls tools over bash for file exploration (faster, respects .gitignore)"
GUIDELINE_CONCISE = "Be concise in your responses"
GUIDELINE_FILE_PATHS = "Show file paths clearly when working with files"


def _build_guidelines(allowed_tools: set[str] | None) -> str:
    """Build dynamic guidelines based on which tools are available."""
    tools = allowed_tools or LLM_VISIBLE_TOOLS
    guidelines = []

    has_bash = "tool_bash" in tools
    has_search_tools = "tool_grep" in tools or "tool_find" in tools or "tool_ls" in tools

    if has_bash and has_search_tools:
        guidelines.append(GUIDELINE_PREFER_TOOLS)
    elif has_bash:
        guidelines.append(GUIDELINE_BASH_ONLY)

    # Tool-specific guidelines
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
    """Build the tools list string for the system prompt."""
    tools = allowed_tools or LLM_VISIBLE_TOOLS
    snippets = {
        "tool_read": "read: Read file contents",
        "tool_write": "write: Create or overwrite files",
        "tool_edit": "edit: Make precise file edits with exact text replacement, including multiple disjoint edits in one call",
        "tool_bash": "bash: Execute bash commands (ls, grep, find, etc.)",
        "tool_grep": "grep: Search file contents for patterns (respects .gitignore)",
        "tool_find": "find: Find files by glob pattern (respects .gitignore)",
        "tool_ls": "ls: List directory contents",
    }
    return "\n".join(f"- {snippets[t]}" for t in sorted(tools) if t in snippets)


def build_system_prompt(pool: ContextPool, allowed_tools: set[str] | None, tools_list: str | None = None) -> str:
    """Assemble the system prompt from ContextPool items in fixed order."""
    parts: list[str] = []

    # Base prompt (or override)
    base_item = pool._items.get("base-prompt")
    if base_item:
        base = str(base_item.content)
        tl = tools_list or _build_tools_list(allowed_tools)
        guidelines = _build_guidelines(allowed_tools)
        base = base.replace("{tools_list}", tl)
        base = base.replace("{guidelines}", guidelines)
        parts.append(base)

    # Active role overlay
    role_item = pool._items.get("active-role")
    if role_item:
        parts.append(str(role_item.content))

    # Project context
    ctx_item = pool._items.get("project-context")
    if ctx_item and str(ctx_item.content).strip():
        parts.append(str(ctx_item.content))

    # Skills index
    skills_item = pool._items.get("skills-index")
    if skills_item and str(skills_item.content).strip():
        parts.append(str(skills_item.content))

    # Append prompt
    append_item = pool._items.get("append-prompt")
    if append_item and str(append_item.content).strip():
        parts.append(str(append_item.content))

    return "\n\n".join(parts)


def build_messages(cq: ContextQueue, compaction_summary: str | None = None) -> list[dict[str, Any]]:
    """Build the messages array from ContextQueue items."""
    messages: list[dict[str, Any]] = []

    if compaction_summary:
        messages.append({
            "role": "system",
            "content": f"[Context from previous conversation]\n{compaction_summary}",
        })

    for item in cq.items:
        if isinstance(item.content, dict):
            messages.append(item.content)

    return messages


def build_tool_schemas(allowed_tools: set[str] | None) -> list[dict[str, Any]]:
    """Build OpenAI-format tool schemas for the LLM from registered pygents tools."""
    tools = allowed_tools or LLM_VISIBLE_TOOLS
    schemas = []

    for t in ToolRegistry.all():
        if t.__name__ not in tools:
            continue
        # Strip "tool_" prefix for the LLM-facing name
        name = t.__name__[5:] if t.__name__.startswith("tool_") else t.__name__
        schema: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": name,
                "description": t.metadata.description or "",
            },
        }
        if t.metadata.input_schema:
            schema["function"]["parameters"] = t.metadata.input_schema
        schemas.append(schema)

    return schemas


# Map LLM-facing tool names back to pygents tool names
TOOL_NAME_MAP = {
    "read": "tool_read",
    "write": "tool_write",
    "edit": "tool_edit",
    "bash": "tool_bash",
    "grep": "tool_grep",
    "find": "tool_find",
    "ls": "tool_ls",
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_llm_call.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add coder/llm_call.py tests/test_llm_call.py
git commit -m "feat: add llm_call helpers for prompt assembly and tool schemas"
```

---

### Task 14: Agent Loop Wiring

**Files:**
- Create: `coder/agent_loop.py`
- Create: `tests/test_agent_loop.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_agent_loop.py
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pygents import Agent, ContextItem, ContextPool, ContextQueue, Turn, tool
from pygents.registry import ToolRegistry

from coder.agent_loop import create_agent, register_all_tools


@pytest.mark.asyncio
async def test_register_all_tools():
    register_all_tools()
    assert ToolRegistry.get("tool_read") is not None
    assert ToolRegistry.get("tool_write") is not None
    assert ToolRegistry.get("tool_edit") is not None
    assert ToolRegistry.get("tool_bash") is not None
    assert ToolRegistry.get("tool_grep") is not None
    assert ToolRegistry.get("tool_find") is not None
    assert ToolRegistry.get("tool_ls") is not None


@pytest.mark.asyncio
async def test_create_agent():
    register_all_tools()
    pool = ContextPool()
    cq = ContextQueue(limit=10)
    agent = create_agent(pool=pool, cq=cq)
    assert agent.name == "coder"
    assert len(agent.tools) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_agent_loop.py -v`
Expected: FAIL

- [ ] **Step 3: Implement agent_loop.py**

```python
# coder/agent_loop.py
import asyncio
from typing import Any

from pygents import Agent, AgentHook, ContextItem, ContextPool, ContextQueue, Turn
from pygents.registry import ToolRegistry

from coder.tools.read import tool_read
from coder.tools.write import tool_write
from coder.tools.edit import tool_edit
from coder.tools.bash import tool_bash
from coder.tools.grep import tool_grep
from coder.tools.find import tool_find
from coder.tools.ls import tool_ls


def register_all_tools() -> list:
    """Import all tool modules to trigger @tool() registration. Returns the tool list."""
    return [tool_read, tool_write, tool_edit, tool_bash, tool_grep, tool_find, tool_ls]


def create_agent(
    pool: ContextPool,
    cq: ContextQueue,
    steering_queue: asyncio.Queue | None = None,
) -> Agent:
    """Create and configure the coder agent with all hooks."""
    tools = register_all_tools()
    agent = Agent("coder", "A coding assistant", tools, context_pool=pool, context_queue=cq)

    # Hook: inject steering messages before each turn
    if steering_queue is not None:
        @agent.before_turn
        async def inject_steering(agent: Agent) -> None:
            while not steering_queue.empty():
                try:
                    msg = steering_queue.get_nowait()
                    await agent.context_queue.append(
                        ContextItem(content={"role": "user", "content": msg})
                    )
                except asyncio.QueueEmpty:
                    break

    return agent
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_agent_loop.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add coder/agent_loop.py tests/test_agent_loop.py
git commit -m "feat: add agent creation with tool registration and steering hook"
```

---

### Task 15: Session Manager

**Files:**
- Create: `coder/session.py`

- [ ] **Step 1: Implement session.py**

```python
# coder/session.py
import asyncio
from dataclasses import dataclass, field

from py_ai_toolkit import LLMConfig, PyAIToolkit
from pygents import Agent, ContextItem, ContextPool, ContextQueue

from coder.agent_loop import create_agent, register_all_tools
from coder.compaction import (
    BRANCH_SUMMARY_PREAMBLE,
    BRANCH_SUMMARY_PROMPT,
    estimate_tokens,
    run_compaction,
    should_compact,
)
from coder.config import SessionConfig, load_config
from coder.personas import PERSONAS, get_persona
from coder.resources import discover_project_context, load_append_prompt, load_system_prompt_override

DEFAULT_BASE_PROMPT = """You are an expert coding assistant operating inside coder, a coding agent harness.
You help users by reading files, executing commands, editing code, and writing new files.

Available tools:
{tools_list}

In addition to the tools above, you may have access to other custom tools depending on the project.

Guidelines:
{guidelines}"""


@dataclass
class Session:
    agent: Agent | None = None
    toolkit: PyAIToolkit | None = None
    pool: ContextPool = field(default_factory=ContextPool)
    cq: ContextQueue = field(default_factory=lambda: ContextQueue(limit=50))
    config: SessionConfig = field(default_factory=SessionConfig)
    steering_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    allowed_tools: set[str] | None = None
    _active_role: str | None = None

    async def start(self, cwd: str | None = None) -> None:
        """Initialize the session: load config, create toolkit, register tools,
        populate context, create agent."""
        # 1. Load config
        self.config = load_config(cwd=cwd)

        # 2. Initialize PyAIToolkit
        llm_config = None
        if self.config.model or self.config.api_key:
            llm_config = LLMConfig(
                model=self.config.model,
                api_key=self.config.api_key,
                base_url=self.config.base_url or None,
            )
        self.toolkit = PyAIToolkit(main_model_config=llm_config)

        # 3. Create ContextQueue
        self.cq = ContextQueue(limit=self.config.history_limit)

        # 4. Create ContextPool and populate
        self.pool = ContextPool()

        # Base prompt (or override)
        override = load_system_prompt_override(self.config.cwd)
        base_prompt = override if override else DEFAULT_BASE_PROMPT
        await self.pool.add(ContextItem(
            id="base-prompt",
            description="Base system prompt",
            content=base_prompt,
        ))

        # Project context
        project_ctx = discover_project_context(self.config.cwd)
        if project_ctx:
            await self.pool.add(ContextItem(
                id="project-context",
                description="Project context from AGENTS.md/CLAUDE.md",
                content=project_ctx,
            ))

        # Append prompt
        append = load_append_prompt(self.config.cwd)
        if append:
            await self.pool.add(ContextItem(
                id="append-prompt",
                description="Appended system prompt instructions",
                content=append,
            ))

        # 5. Create agent
        self.agent = create_agent(
            pool=self.pool,
            cq=self.cq,
            steering_queue=self.steering_queue,
        )

    async def switch_role(self, persona_name: str) -> None:
        """Switch to a subagent persona: update system prompt, model, tool filter."""
        persona = get_persona(persona_name)

        # Summarize current branch if there's history
        if len(self.cq) > 0 and self.toolkit:
            conversation = "\n".join(
                f"[{item.content.get('role', '?')}]: {item.content.get('content', '')}"
                for item in self.cq.items
                if isinstance(item.content, dict)
            )
            response = await self.toolkit.chat(
                template="{{ conversation }}\n\n{{ prompt }}",
                conversation=conversation,
                prompt=BRANCH_SUMMARY_PROMPT,
            )
            # Store branch summary in pool
            try:
                await self.pool.remove("branch-summary")
            except KeyError:
                pass
            await self.pool.add(ContextItem(
                id="branch-summary",
                description="Summary of previous conversation branch",
                content=BRANCH_SUMMARY_PREAMBLE + response.content,
            ))

        # Update active role
        try:
            await self.pool.remove("active-role")
        except KeyError:
            pass
        await self.pool.add(ContextItem(
            id="active-role",
            description=f"Active role: {persona.name}",
            content=persona.system_prompt,
        ))

        # Update tool filter
        self.allowed_tools = set(persona.allowed_tools)

        # Update model config
        if self.toolkit and persona.model_hint:
            # Model hints are advisory — the actual model name depends on the provider
            pass  # User configures actual model names in config

        self._active_role = persona_name

    async def clear_role(self) -> None:
        """Remove the active persona, returning to default."""
        try:
            await self.pool.remove("active-role")
        except KeyError:
            pass
        self.allowed_tools = None
        self._active_role = None

    async def check_compaction(self) -> None:
        """Check if compaction is needed and run it if so."""
        if not self.toolkit:
            return

        items = self.cq.items
        # Use a rough max context tokens estimate (128k tokens for most models)
        max_tokens = 128000
        if not should_compact(items, self.config.compaction_threshold, max_tokens):
            return

        existing_summary = None
        try:
            summary_item = self.pool.get("compaction-summary")
            existing_summary = str(summary_item.content)
        except KeyError:
            pass

        summary, recent = await run_compaction(
            self.toolkit, items, existing_summary, self.config.keep_recent_tokens
        )

        # Store summary
        try:
            await self.pool.remove("compaction-summary")
        except KeyError:
            pass
        await self.pool.add(ContextItem(
            id="compaction-summary",
            description="Compacted conversation summary",
            content=summary,
        ))

        # Replace queue with recent messages only
        await self.cq.clear()
        for item in recent:
            await self.cq.append(item)
```

- [ ] **Step 2: Commit**

```bash
git add coder/session.py
git commit -m "feat: add session manager with startup, role switching, and compaction"
```

---

### Task 16: CLI Entry Point

**Files:**
- Create: `coder/cli.py`

- [ ] **Step 1: Implement cli.py**

```python
# coder/cli.py
import asyncio
import sys

from pygents import ContextItem, Turn

from coder.prompts import is_slash_command, list_slash_commands, load_slash_command
from coder.session import Session


async def read_user_input() -> str | None:
    """Read a line from stdin asynchronously. Returns None on EOF."""
    loop = asyncio.get_event_loop()
    try:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            return None
        return line.rstrip("\n")
    except (EOFError, KeyboardInterrupt):
        return None


async def handle_input(session: Session, user_input: str) -> str | None:
    """Process user input: slash commands, role switching, or regular messages.
    Returns the message to send to the LLM, or None if handled internally."""

    # Slash commands
    if is_slash_command(user_input):
        expanded = load_slash_command(user_input, cwd=session.config.cwd)
        if expanded is None:
            commands = list_slash_commands(cwd=session.config.cwd)
            if commands:
                print(f"Unknown command. Available: {', '.join('/' + c for c in commands)}")
            else:
                print("No slash commands found in .coder/prompts/")
            return None
        return expanded

    # Built-in commands
    if user_input.strip() == "/help":
        commands = list_slash_commands(cwd=session.config.cwd)
        print("Built-in commands:")
        print("  /help          - Show this help")
        print("  /role <name>   - Switch persona (scout, planner, worker, reviewer)")
        print("  /role          - Clear active persona")
        print("  /quit          - Exit")
        if commands:
            print("\nSlash commands:")
            for cmd in commands:
                print(f"  /{cmd}")
        return None

    if user_input.strip().startswith("/role"):
        parts = user_input.strip().split(None, 1)
        if len(parts) == 1:
            await session.clear_role()
            print("Cleared active role.")
        else:
            role_name = parts[1].strip()
            try:
                await session.switch_role(role_name)
                print(f"Switched to {role_name} role.")
            except KeyError:
                print(f"Unknown role: {role_name}. Available: scout, planner, worker, reviewer")
        return None

    if user_input.strip() in ("/quit", "/exit"):
        return None

    return user_input


async def main(cwd: str | None = None) -> None:
    """Main CLI loop."""
    session = Session()
    await session.start(cwd=cwd)

    print("coder ready. Type /help for commands, /quit to exit.\n")

    while True:
        try:
            sys.stdout.write("> ")
            sys.stdout.flush()
            user_input = await read_user_input()

            if user_input is None or user_input.strip() in ("/quit", "/exit"):
                print("\nGoodbye.")
                break

            if not user_input.strip():
                continue

            message = await handle_input(session, user_input)
            if message is None:
                continue

            # Add user message to context
            await session.cq.append(
                ContextItem(content={"role": "user", "content": message})
            )

            # Check compaction before LLM call
            await session.check_compaction()

            # TODO: enqueue Turn(llm_call) and run agent loop
            # This will be wired up when llm_call is integrated with the streaming LLM
            # For now, print a placeholder
            print("[Agent would process message here]")
            print()

        except KeyboardInterrupt:
            print("\n\nInterrupted. Type /quit to exit.")
            continue
```

- [ ] **Step 2: Update main.py**

```python
# main.py
import asyncio

from coder.cli import main

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Verify the CLI starts**

Run: `echo "/quit" | uv run python main.py`
Expected: prints "coder ready" then "Goodbye."

- [ ] **Step 4: Commit**

```bash
git add coder/cli.py main.py
git commit -m "feat: add CLI with slash commands, role switching, and main loop"
```

---

### Task 17: Integration — Wire llm_call to Streaming LLM

**Files:**
- Modify: `coder/llm_call.py`
- Modify: `coder/agent_loop.py`
- Modify: `coder/cli.py`

This task connects the LLM call to py-ai-toolkit's streaming API and wires the agent loop end-to-end. This is the integration point where all previous tasks come together.

- [ ] **Step 1: Add the llm_call tool function to llm_call.py**

Append to `coder/llm_call.py`:

```python
# Add these imports at the top of coder/llm_call.py
# (alongside existing imports)
from py_ai_toolkit import PyAIToolkit


async def run_llm_call(
    toolkit: PyAIToolkit,
    cq: ContextQueue,
    pool: ContextPool,
    allowed_tools: set[str] | None = None,
) -> list[dict[str, Any]] | str:
    """Call the LLM with current context. Streams text to stdout.

    Returns:
        - A list of tool call dicts if the LLM wants to call tools
        - A string with the response text if no tool calls
    """
    # Build system prompt
    system_prompt = build_system_prompt(pool, allowed_tools)

    # Build messages
    compaction_summary = None
    try:
        summary_item = pool.get("compaction-summary")
        compaction_summary = str(summary_item.content)
    except KeyError:
        pass
    messages = build_messages(cq, compaction_summary=compaction_summary)

    # Build tool schemas
    schemas = build_tool_schemas(allowed_tools)

    # Call LLM via streaming
    full_response = ""
    async for chunk in toolkit.stream(
        template="{{ system_prompt }}\n\n{% for msg in messages %}[{{ msg.role }}]: {{ msg.content }}\n{% endfor %}",
        system_prompt=system_prompt,
        messages=messages,
    ):
        text = chunk.content
        if text:
            sys.stdout.write(text)
            sys.stdout.flush()
            full_response += text

    print()  # newline after streaming

    # For now, return the text response
    # TODO: Parse tool calls from structured response when using tool-use API
    return full_response
```

- [ ] **Step 2: Update agent_loop.py to wire the run loop**

Add to `coder/agent_loop.py`:

```python
# Add to imports at top of coder/agent_loop.py
from coder.llm_call import run_llm_call
from coder.compaction import should_compact


async def run_agent_loop(
    session,  # Session instance (avoid circular import)
) -> None:
    """Run the agent's main loop: call LLM, execute tools, repeat."""
    while True:
        # Check compaction before LLM call
        await session.check_compaction()

        # Inject any steering messages
        while not session.steering_queue.empty():
            try:
                msg = session.steering_queue.get_nowait()
                await session.cq.append(
                    ContextItem(content={"role": "user", "content": msg})
                )
            except asyncio.QueueEmpty:
                break

        # Call LLM
        result = await run_llm_call(
            toolkit=session.toolkit,
            cq=session.cq,
            pool=session.pool,
            allowed_tools=session.allowed_tools,
        )

        # Append assistant response to context
        if isinstance(result, str):
            await session.cq.append(
                ContextItem(content={"role": "assistant", "content": result})
            )
            break  # No tool calls, conversation turn complete

        # If tool calls came back, execute them and continue
        # (tool call parsing will be implemented with proper tool-use API integration)
        break
```

- [ ] **Step 3: Update cli.py to use run_agent_loop**

Replace the TODO placeholder in `coder/cli.py`'s main loop:

```python
# In coder/cli.py, replace:
#     # TODO: enqueue Turn(llm_call) and run agent loop
#     print("[Agent would process message here]")
#     print()
# With:
            from coder.agent_loop import run_agent_loop
            await run_agent_loop(session)
            print()
```

- [ ] **Step 4: Test end-to-end manually**

Run: `echo "What is 2+2?" | LLM_MODEL=claude-sonnet-4-5 LLM_API_KEY=your-key uv run python main.py`
Expected: streams a response about 2+2 being 4, then exits

- [ ] **Step 5: Commit**

```bash
git add coder/llm_call.py coder/agent_loop.py coder/cli.py
git commit -m "feat: wire llm_call to streaming LLM and integrate agent loop"
```

---

### Task 18: End-to-End Smoke Test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pygents import ContextItem, ContextPool, ContextQueue

from coder.session import Session


@pytest.mark.asyncio
async def test_session_start(tmp_path):
    """Test that session starts and populates context pool."""
    session = Session()
    with patch.dict("os.environ", {"LLM_MODEL": "test-model", "LLM_API_KEY": "test-key"}):
        await session.start(cwd=str(tmp_path))

    assert session.agent is not None
    assert session.agent.name == "coder"
    assert session.pool.get("base-prompt") is not None
    assert session.toolkit is not None


@pytest.mark.asyncio
async def test_session_with_project_context(tmp_path):
    """Test that AGENTS.md is discovered and loaded."""
    (tmp_path / "AGENTS.md").write_text("Be helpful and concise.")
    session = Session()
    with patch.dict("os.environ", {"LLM_MODEL": "test-model", "LLM_API_KEY": "test-key"}):
        await session.start(cwd=str(tmp_path))

    ctx = session.pool.get("project-context")
    assert "Be helpful" in str(ctx.content)


@pytest.mark.asyncio
async def test_session_role_switching(tmp_path):
    """Test switching to scout role."""
    session = Session()
    with patch.dict("os.environ", {"LLM_MODEL": "test-model", "LLM_API_KEY": "test-key"}):
        await session.start(cwd=str(tmp_path))

    # Mock toolkit.chat to avoid real LLM calls
    session.toolkit.chat = AsyncMock(return_value=MagicMock(content="Branch summary"))

    await session.switch_role("scout")
    role = session.pool.get("active-role")
    assert "scout" in str(role.content).lower() or "investigate" in str(role.content).lower()
    assert session.allowed_tools is not None
    assert "tool_write" not in session.allowed_tools


@pytest.mark.asyncio
async def test_session_compaction(tmp_path):
    """Test that compaction produces a summary when context is large."""
    session = Session()
    with patch.dict("os.environ", {"LLM_MODEL": "test-model", "LLM_API_KEY": "test-key"}):
        await session.start(cwd=str(tmp_path))

    session.toolkit.chat = AsyncMock(return_value=MagicMock(content="## Goal\nTest goal"))

    # Fill context queue with enough content to trigger compaction
    for i in range(40):
        await session.cq.append(
            ContextItem(content={"role": "user", "content": f"Message {i} " + "x" * 5000})
        )

    # Force low threshold
    session.config.compaction_threshold = 0.01
    await session.check_compaction()

    summary = session.pool.get("compaction-summary")
    assert "Goal" in str(summary.content)
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/test_integration.py -v`
Expected: all tests PASS

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for session lifecycle"
```

---

## Summary

| Task | Component | Files |
|------|-----------|-------|
| 1 | Project scaffolding | pyproject.toml, constants, conftest |
| 2 | Tool: read | tools/read.py |
| 3 | Tool: write | tools/write.py |
| 4 | Tool: edit | tools/edit.py |
| 5 | Tool: bash | tools/bash.py |
| 6 | Tool: grep | tools/grep.py |
| 7 | Tool: find | tools/find.py |
| 8 | Tool: ls | tools/ls.py |
| 9 | Config + resources | config.py, resources.py |
| 10 | Slash commands | prompts.py |
| 11 | Compaction | compaction.py |
| 12 | Personas | personas.py |
| 13 | llm_call helpers | llm_call.py |
| 14 | Agent loop | agent_loop.py |
| 15 | Session manager | session.py |
| 16 | CLI | cli.py |
| 17 | Integration wiring | llm_call + agent_loop + cli |
| 18 | Smoke tests | test_integration.py |
