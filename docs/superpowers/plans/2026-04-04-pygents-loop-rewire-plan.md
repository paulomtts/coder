# Pygents Loop Rewire Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure coder's agent loop to use pygents `Agent.run()` with tool-driven flow control, splitting `llm_call` into `llm_decide` (structured) and `llm_respond` (streaming).

**Architecture:** Two pygents tools (`llm_decide`, `llm_respond`) drive the agent loop. `llm_decide` makes structured LLM calls and yields `Turn` objects for tool execution or `Turn(llm_respond)` for final output. File/shell tools yield `ContextItem` results. The REPL consumes `agent.run()` and prints streamed text from `llm_respond`. Steering is injected via `before_turn` hook; compaction via `before_invoke` hook on `llm_decide`.

**Tech Stack:** pygents (Agent, Turn, ContextQueue, ContextPool, ContextItem, @tool), py-ai-toolkit (PyAIToolkit, asend, stream), pydantic (AgentResponse model)

---

### Task 1: Create `llm_decide` tool

**Files:**
- Create: `coder/agent/llm/decide.py`
- Test: `tests/test_llm_decide.py`
- Reference: `coder/agent/llm/prompt.py` (read-only, used by llm_decide)
- Reference: `coder/agent/llm/call.py` (read-only, existing code to port from)

- [ ] **Step 1: Write the failing test for llm_decide yielding Turn when tool calls present**

```python
# tests/test_llm_decide.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from pygents import ContextItem, ContextPool, ContextQueue, Turn
from pygents.registry import ToolRegistry

from coder.agent.llm.decide import llm_decide, AgentResponse, ToolCallRequest


@pytest.fixture
def pool():
    pool = ContextPool()
    pool._items["base-prompt"] = ContextItem(
        id="base-prompt",
        description="Base system prompt",
        content="You are a coding assistant.\n\nAvailable tools:\n{tools_list}\n\nGuidelines:\n{guidelines}",
    )
    return pool


@pytest.fixture
def cq():
    cq = ContextQueue(limit=10)
    cq._items.append(ContextItem(content={"role": "user", "content": "Read foo.py"}))
    return cq


@pytest.mark.asyncio
async def test_llm_decide_yields_tool_turns(pool, cq):
    """When LLM returns tool calls, llm_decide yields ContextItem + Turn per tool + Turn(llm_decide)."""
    mock_toolkit = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = AgentResponse(
        text=None,
        tool_calls=[ToolCallRequest(name="tool_read", arguments={"path": "foo.py"})],
    )
    mock_toolkit.asend = AsyncMock(return_value=mock_response)

    yielded = []
    async for value in llm_decide(cq=cq, pool=pool, toolkit=mock_toolkit):
        yielded.append(value)

    # First yield: ContextItem (assistant message)
    assert isinstance(yielded[0], ContextItem)
    assert yielded[0].content["role"] == "assistant"

    # Second yield: Turn for tool_read
    assert isinstance(yielded[1], Turn)
    assert yielded[1].tool.metadata.name == "tool_read"

    # Third yield: Turn for llm_decide (self-enqueue)
    assert isinstance(yielded[2], Turn)
    assert yielded[2].tool.metadata.name == "llm_decide"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_llm_decide.py::test_llm_decide_yields_tool_turns -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coder.agent.llm.decide'`

- [ ] **Step 3: Write the llm_decide tool**

```python
# coder/agent/llm/decide.py
from typing import Any

from pydantic import BaseModel, Field
from pygents import ContextItem, ContextPool, ContextQueue, Turn, tool
from py_ai_toolkit import PyAIToolkit

from coder.agent.llm.prompt import build_system_prompt, build_messages, build_tool_schemas


class ToolCallRequest(BaseModel):
    """A single tool call requested by the LLM."""

    name: str = Field(description="Tool name (e.g. tool_read, tool_write)")
    arguments: dict[str, Any] = Field(description="Arguments to pass to the tool")


class AgentResponse(BaseModel):
    """The LLM's response: either a text reply, or one or more tool calls."""

    text: str | None = Field(
        None, description="Text response to the user. Set when no tools need to be called."
    )
    tool_calls: list[ToolCallRequest] | None = Field(
        None, description="Tools to call. Set when you need to use tools before responding."
    )


@tool()
async def llm_decide(cq: ContextQueue, pool: ContextPool, toolkit: PyAIToolkit):
    """Structured LLM call that decides: execute tools or respond to user."""
    allowed_tools = _get_allowed_tools(pool)
    system_prompt = build_system_prompt(pool, allowed_tools)
    compaction_summary = _get_compaction_summary(pool)
    messages = build_messages(cq, compaction_summary)
    tool_schemas = build_tool_schemas(allowed_tools)

    # Build conversation string from messages
    history_parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if content:
            history_parts.append(f"[{role}]: {content}")
    conversation = "\n\n".join(history_parts)

    # Build tool reference string
    tool_ref = "\n".join(
        f"- {s['function']['name']}: {s['function'].get('description', '')}"
        for s in tool_schemas
    )

    response = await toolkit.asend(
        response_model=AgentResponse,
        template=(
            "{{ system_prompt }}\n\n"
            "## Available Tools\n{{ tool_ref }}\n\n"
            "## Conversation\n{{ conversation }}"
        ),
        system_prompt=system_prompt,
        tool_ref=tool_ref,
        conversation=conversation,
    )

    agent_response = response.content

    # Yield assistant message -> agent routes to cq
    assistant_content = ""
    if agent_response.text:
        assistant_content = agent_response.text
    if agent_response.tool_calls:
        calls_desc = ", ".join(
            f"{tc.name}({tc.arguments})" for tc in agent_response.tool_calls
        )
        assistant_content = (
            f"{assistant_content}\nCalling: {calls_desc}" if assistant_content else f"Calling: {calls_desc}"
        )
    yield ContextItem(content={"role": "assistant", "content": assistant_content})

    # Route next step
    if agent_response.tool_calls:
        for tc in agent_response.tool_calls:
            yield Turn(tc.name, kwargs=tc.arguments)
        yield Turn(llm_decide)  # self-enqueue after all tools (FIFO)
    else:
        from coder.agent.llm.respond import llm_respond

        yield Turn(llm_respond)


def _get_allowed_tools(pool: ContextPool) -> set[str] | None:
    """Read allowed_tools from pool if a persona filter is active."""
    try:
        item = pool.get("allowed-tools")
        tools = item.content
        if isinstance(tools, set):
            return tools
        return None
    except KeyError:
        return None


def _get_compaction_summary(pool: ContextPool) -> str | None:
    """Read compaction summary from pool if present."""
    try:
        item = pool.get("compaction-summary")
        return str(item.content)
    except KeyError:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_llm_decide.py::test_llm_decide_yields_tool_turns -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for llm_decide yielding Turn(llm_respond) when no tool calls**

```python
# tests/test_llm_decide.py (append)

@pytest.mark.asyncio
async def test_llm_decide_yields_respond_turn_when_no_tools(pool, cq):
    """When LLM returns text only, llm_decide yields ContextItem + Turn(llm_respond)."""
    mock_toolkit = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = AgentResponse(
        text="The file contains a greeting function.",
        tool_calls=None,
    )
    mock_toolkit.asend = AsyncMock(return_value=mock_response)

    yielded = []
    async for value in llm_decide(cq=cq, pool=pool, toolkit=mock_toolkit):
        yielded.append(value)

    # First yield: ContextItem (assistant message)
    assert isinstance(yielded[0], ContextItem)
    assert yielded[0].content["role"] == "assistant"

    # Second yield: Turn(llm_respond)
    assert isinstance(yielded[1], Turn)
    assert yielded[1].tool.metadata.name == "llm_respond"
```

- [ ] **Step 6: Run test to verify it passes** (should pass with existing implementation)

Run: `uv run pytest tests/test_llm_decide.py -v`
Expected: PASS (both tests)

- [ ] **Step 7: Write the failing test for multiple tool calls**

```python
# tests/test_llm_decide.py (append)

@pytest.mark.asyncio
async def test_llm_decide_yields_multiple_tool_turns(pool, cq):
    """Multiple tool calls yield one Turn per tool plus self-enqueue."""
    mock_toolkit = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = AgentResponse(
        text=None,
        tool_calls=[
            ToolCallRequest(name="tool_read", arguments={"path": "a.py"}),
            ToolCallRequest(name="tool_read", arguments={"path": "b.py"}),
            ToolCallRequest(name="tool_grep", arguments={"pattern": "def main"}),
        ],
    )
    mock_toolkit.asend = AsyncMock(return_value=mock_response)

    yielded = []
    async for value in llm_decide(cq=cq, pool=pool, toolkit=mock_toolkit):
        yielded.append(value)

    # ContextItem + 3 tool turns + 1 self-enqueue = 5
    assert len(yielded) == 5
    assert isinstance(yielded[0], ContextItem)
    assert all(isinstance(y, Turn) for y in yielded[1:])
    assert yielded[-1].tool.metadata.name == "llm_decide"
```

- [ ] **Step 8: Run all tests to verify they pass**

Run: `uv run pytest tests/test_llm_decide.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 9: Commit**

```bash
git add coder/agent/llm/decide.py tests/test_llm_decide.py
git commit -m "feat: add llm_decide tool for structured LLM decisions"
```

---

### Task 2: Create `llm_respond` tool

**Files:**
- Create: `coder/agent/llm/respond.py`
- Test: `tests/test_llm_respond.py`

- [ ] **Step 1: Write the failing test for llm_respond streaming**

```python
# tests/test_llm_respond.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from pygents import ContextItem, ContextPool, ContextQueue

from coder.agent.llm.respond import llm_respond


@pytest.fixture
def pool():
    pool = ContextPool()
    pool._items["base-prompt"] = ContextItem(
        id="base-prompt",
        description="Base system prompt",
        content="You are a coding assistant.\n\nAvailable tools:\n{tools_list}\n\nGuidelines:\n{guidelines}",
    )
    return pool


@pytest.fixture
def cq():
    cq = ContextQueue(limit=10)
    cq._items.append(ContextItem(content={"role": "user", "content": "Hello"}))
    return cq


async def _fake_stream(*args, **kwargs):
    """Simulate toolkit.stream() yielding chunks."""
    chunks = ["Hello", ", ", "world", "!"]
    for text in chunks:
        chunk = MagicMock()
        chunk.content = text
        yield chunk


@pytest.mark.asyncio
async def test_llm_respond_yields_chunks_then_context_item(pool, cq):
    """llm_respond yields text chunks then a final ContextItem."""
    mock_toolkit = MagicMock()
    mock_toolkit.stream = _fake_stream

    yielded = []
    async for value in llm_respond(cq=cq, pool=pool, toolkit=mock_toolkit):
        yielded.append(value)

    # First 4 yields: text chunks
    assert yielded[0] == "Hello"
    assert yielded[1] == ", "
    assert yielded[2] == "world"
    assert yielded[3] == "!"

    # Last yield: ContextItem with full text
    assert isinstance(yielded[4], ContextItem)
    assert yielded[4].content["role"] == "assistant"
    assert yielded[4].content["content"] == "Hello, world!"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_llm_respond.py::test_llm_respond_yields_chunks_then_context_item -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coder.agent.llm.respond'`

- [ ] **Step 3: Write the llm_respond tool**

```python
# coder/agent/llm/respond.py
from pygents import ContextItem, ContextPool, ContextQueue, tool
from py_ai_toolkit import PyAIToolkit

from coder.agent.llm.prompt import build_system_prompt, build_messages


@tool()
async def llm_respond(cq: ContextQueue, pool: ContextPool, toolkit: PyAIToolkit):
    """Streaming LLM call that yields text chunks for the REPL to print."""
    from coder.agent.llm.decide import _get_allowed_tools, _get_compaction_summary

    allowed_tools = _get_allowed_tools(pool)
    system_prompt = build_system_prompt(pool, allowed_tools)
    compaction_summary = _get_compaction_summary(pool)
    messages = build_messages(cq, compaction_summary)

    # Build conversation string from messages
    history_parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if content:
            history_parts.append(f"[{role}]: {content}")
    conversation = "\n\n".join(history_parts)

    full_text = ""
    async for chunk in toolkit.stream(
        template="{{ system_prompt }}\n\n## Conversation\n{{ conversation }}",
        system_prompt=system_prompt,
        conversation=conversation,
    ):
        full_text += chunk.content
        yield chunk.content

    yield ContextItem(content={"role": "assistant", "content": full_text})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_llm_respond.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coder/agent/llm/respond.py tests/test_llm_respond.py
git commit -m "feat: add llm_respond tool for streaming final text"
```

---

### Task 3: Convert file/shell tools to yield ContextItem

**Files:**
- Modify: `coder/agent/tools/read.py`
- Modify: `coder/agent/tools/write.py`
- Modify: `coder/agent/tools/edit.py`
- Modify: `coder/agent/tools/bash.py`
- Modify: `coder/agent/tools/grep.py`
- Modify: `coder/agent/tools/find.py`
- Modify: `coder/agent/tools/ls.py`
- Modify: `tests/test_tools_read.py` (and other test_tools_* files)

Each tool currently returns a `str`. It must become an async generator that yields a `ContextItem(content={"role": "tool", "content": result})`.

- [ ] **Step 1: Write the failing test for tool_read yielding ContextItem**

```python
# tests/test_tools_read.py (add this test)

@pytest.mark.asyncio
async def test_tool_read_yields_context_item(tmp_path):
    """tool_read yields a ContextItem, not a plain string."""
    from pygents import ContextItem

    f = tmp_path / "hello.txt"
    f.write_text("hello world")

    yielded = []
    async for value in tool_read(str(f)):
        yielded.append(value)

    assert len(yielded) == 1
    assert isinstance(yielded[0], ContextItem)
    assert yielded[0].content["role"] == "tool"
    assert "hello world" in yielded[0].content["content"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tools_read.py::test_tool_read_yields_context_item -v`
Expected: FAIL — tool_read returns a string, not an async generator

- [ ] **Step 3: Convert tool_read to yield ContextItem**

Replace the return statements in `coder/agent/tools/read.py` with yields:

```python
# coder/agent/tools/read.py
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
        result = _truncate_output(content, MAX_LINES, MAX_BYTES)
        yield ContextItem(content={"role": "tool", "content": result})
    except Exception as e:
        yield ContextItem(content={"role": "tool", "content": f"Error reading {path}: {e}"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tools_read.py::test_tool_read_yields_context_item -v`
Expected: PASS

- [ ] **Step 5: Update existing tool_read tests**

Existing tests use `result = await tool_read(...)` which won't work with generators. Update them to collect yielded values:

```python
# In each existing test, replace:
#   result = await tool_read(str(path))
# With:
#   values = [v async for v in tool_read(str(path))]
#   result = values[0].content["content"]
```

- [ ] **Step 6: Run all tool_read tests**

Run: `uv run pytest tests/test_tools_read.py -v`
Expected: PASS

- [ ] **Step 7: Convert tool_write to yield ContextItem**

```python
# coder/agent/tools/write.py
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
```

- [ ] **Step 8: Update tool_write tests and run**

Run: `uv run pytest tests/test_tools_write.py -v`
Expected: PASS

- [ ] **Step 9: Convert tool_edit to yield ContextItem**

Same pattern: replace `return result` with `yield ContextItem(content={"role": "tool", "content": result})`.

- [ ] **Step 10: Update tool_edit tests and run**

Run: `uv run pytest tests/test_tools_edit.py -v`
Expected: PASS

- [ ] **Step 11: Convert tool_bash to yield ContextItem**

Same pattern. Replace `return` with `yield ContextItem(...)`.

```python
# coder/agent/tools/bash.py — key change in tool_bash:
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
```

- [ ] **Step 12: Update tool_bash tests and run**

Run: `uv run pytest tests/test_tools_bash.py -v`
Expected: PASS

- [ ] **Step 13: Convert tool_grep, tool_find, tool_ls to yield ContextItem**

Same pattern for all three. Replace `return` with `yield ContextItem(...)`.

- [ ] **Step 14: Update tool_grep, tool_find, tool_ls tests and run**

Run: `uv run pytest tests/test_tools_grep.py tests/test_tools_find.py tests/test_tools_ls.py -v`
Expected: PASS

- [ ] **Step 15: Run all tests**

Run: `uv run pytest -v`
Expected: PASS (some tests in test_agent_loop.py and test_llm_call.py may fail — those will be updated in later tasks)

- [ ] **Step 16: Commit**

```bash
git add coder/agent/tools/ tests/test_tools_*.py
git commit -m "refactor: convert all tools to yield ContextItem instead of returning str"
```

---

### Task 4: Rewrite `loop.py` — agent creation with hook wiring

**Files:**
- Modify: `coder/agent/loop.py`
- Modify: `tests/test_agent_loop.py`

- [ ] **Step 1: Write the failing test for create_agent with llm tools**

```python
# tests/test_agent_loop.py (replace existing content)
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from pygents import ContextItem, ContextPool, ContextQueue
from pygents.registry import ToolRegistry

from coder.agent.loop import create_agent


@pytest.mark.asyncio
async def test_create_agent_has_all_tools():
    """Agent should have file/shell tools + llm_decide + llm_respond."""
    session = MagicMock()
    session.toolkit = MagicMock()
    session.steering_queue = asyncio.Queue()
    session.config = MagicMock()
    session.config.compaction_threshold = 0.8
    session.config.keep_recent_tokens = 20000

    pool = ContextPool()
    cq = ContextQueue(limit=10)
    agent = create_agent(session=session, pool=pool, cq=cq)

    tool_names = {t.metadata.name for t in agent.tools}
    assert "tool_read" in tool_names
    assert "tool_write" in tool_names
    assert "tool_edit" in tool_names
    assert "tool_bash" in tool_names
    assert "tool_grep" in tool_names
    assert "tool_find" in tool_names
    assert "tool_ls" in tool_names
    assert "llm_decide" in tool_names
    assert "llm_respond" in tool_names


@pytest.mark.asyncio
async def test_create_agent_name():
    session = MagicMock()
    session.toolkit = MagicMock()
    session.steering_queue = asyncio.Queue()
    session.config = MagicMock()
    session.config.compaction_threshold = 0.8
    session.config.keep_recent_tokens = 20000

    pool = ContextPool()
    cq = ContextQueue(limit=10)
    agent = create_agent(session=session, pool=pool, cq=cq)
    assert agent.name == "coder"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_agent_loop.py -v`
Expected: FAIL — `create_agent` has wrong signature

- [ ] **Step 3: Rewrite loop.py**

```python
# coder/agent/loop.py
import asyncio

from pygents import Agent, ContextItem, ContextPool, ContextQueue, Turn, tool
from pygents.registry import ToolRegistry
from py_ai_toolkit import PyAIToolkit

from coder.agent.tools import ALL_TOOLS
from coder.agent.compaction.summarizer import run_compaction, should_compact


def _register_tools(tools: list) -> None:
    for t in tools:
        if ToolRegistry._registry.get(t.__name__) is None:
            ToolRegistry.register(t)


def create_agent(session, pool: ContextPool, cq: ContextQueue) -> Agent:
    """Create the pygents agent with all tools, llm_decide, llm_respond, and hooks."""
    # Import here to avoid circular imports — llm tools are defined in their own modules
    from coder.agent.llm.decide import llm_decide
    from coder.agent.llm.respond import llm_respond

    all_tools = list(ALL_TOOLS) + [llm_decide, llm_respond]
    _register_tools(all_tools)

    agent = Agent(
        "coder",
        "A coding assistant",
        all_tools,
        context_pool=pool,
        context_queue=cq,
    )

    # Hook: inject steering messages before llm_decide turns
    @agent.before_turn
    async def inject_steering(agent: Agent) -> None:
        if agent.current_turn.tool.metadata.name != "llm_decide":
            return
        while not session.steering_queue.empty():
            try:
                msg = session.steering_queue.get_nowait()
                await agent.context_queue.append(
                    ContextItem(content={"role": "user", "content": msg})
                )
            except asyncio.QueueEmpty:
                break

    # Hook: compaction before llm_decide invocation
    @llm_decide.before_invoke
    async def check_compaction(
        cq: ContextQueue, pool: ContextPool, toolkit: PyAIToolkit
    ) -> None:
        items = cq.items
        max_tokens = 128_000
        if not should_compact(items, session.config.compaction_threshold, max_tokens):
            return
        existing_summary = None
        try:
            summary_item = pool.get("compaction-summary")
            existing_summary = str(summary_item.content)
        except KeyError:
            pass
        summary, recent = await run_compaction(
            toolkit, items, existing_summary, session.config.keep_recent_tokens
        )
        try:
            await pool.remove("compaction-summary")
        except KeyError:
            pass
        await pool.add(
            ContextItem(
                id="compaction-summary",
                description="Compacted conversation summary",
                content=summary,
            )
        )
        await cq.clear()
        for item in recent:
            await cq.append(item)

    return agent
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_agent_loop.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coder/agent/loop.py tests/test_agent_loop.py
git commit -m "refactor: rewrite loop.py with pygents agent creation and hook wiring"
```

---

### Task 5: Update `session.py` to use new agent creation

**Files:**
- Modify: `coder/agent/session.py`
- Modify: `tests/test_personas.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_personas.py (add test)

@pytest.mark.asyncio
async def test_switch_role_stores_allowed_tools_in_pool():
    """switch_role should store allowed_tools in the pool for llm_decide to read."""
    from coder.agent.session import Session

    session = Session()
    # Minimal setup — mock toolkit to avoid real LLM calls
    session.toolkit = AsyncMock()
    session.toolkit.chat = AsyncMock(return_value=MagicMock(content="Branch summary"))
    session.cq = ContextQueue(limit=10)
    session.pool = ContextPool()

    await session.switch_role("scout")

    # allowed_tools should be stored in pool
    item = session.pool.get("allowed-tools")
    assert item is not None
    assert "tool_read" in item.content
    assert "tool_write" not in item.content  # scout can't write
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_personas.py::test_switch_role_stores_allowed_tools_in_pool -v`
Expected: FAIL — current switch_role sets `self.allowed_tools` on session, not in pool

- [ ] **Step 3: Update session.py**

```python
# coder/agent/session.py
import asyncio
from dataclasses import dataclass, field

from py_ai_toolkit import LLMConfig, PyAIToolkit
from pygents import Agent, ContextItem, ContextPool, ContextQueue

from coder.agent.loop import create_agent
from coder.agent.compaction.prompts import (
    BRANCH_SUMMARY_PREAMBLE,
    BRANCH_SUMMARY_PROMPT,
)
from coder.config.loader import SessionConfig, load_config
from coder.agent.personas.definitions import get_persona
from coder.config.resources import (
    discover_project_context,
    load_append_prompt,
    load_system_prompt_override,
)

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
    _active_role: str | None = None

    async def start(self, cwd: str | None = None) -> None:
        self.config = load_config(cwd=cwd)
        llm_config = None
        if self.config.model or self.config.api_key:
            llm_config = LLMConfig(
                model=self.config.model,
                api_key=self.config.api_key,
                base_url=self.config.base_url or None,
            )
        self.toolkit = PyAIToolkit(main_model_config=llm_config)
        self.cq = ContextQueue(limit=self.config.history_limit)
        self.pool = ContextPool()
        override = load_system_prompt_override(self.config.cwd)
        base_prompt = override if override else DEFAULT_BASE_PROMPT
        await self.pool.add(
            ContextItem(
                id="base-prompt", description="Base system prompt", content=base_prompt
            )
        )
        project_ctx = discover_project_context(self.config.cwd)
        if project_ctx:
            await self.pool.add(
                ContextItem(
                    id="project-context",
                    description="Project context from AGENTS.md/CLAUDE.md",
                    content=project_ctx,
                )
            )
        append = load_append_prompt(self.config.cwd)
        if append:
            await self.pool.add(
                ContextItem(
                    id="append-prompt",
                    description="Appended system prompt instructions",
                    content=append,
                )
            )
        self.agent = create_agent(session=self, pool=self.pool, cq=self.cq)

    async def switch_role(self, persona_name: str) -> None:
        persona = get_persona(persona_name)
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
            try:
                await self.pool.remove("branch-summary")
            except KeyError:
                pass
            await self.pool.add(
                ContextItem(
                    id="branch-summary",
                    description="Summary of previous conversation branch",
                    content=BRANCH_SUMMARY_PREAMBLE + response.content,
                )
            )
        try:
            await self.pool.remove("active-role")
        except KeyError:
            pass
        await self.pool.add(
            ContextItem(
                id="active-role",
                description=f"Active role: {persona.name}",
                content=persona.system_prompt,
            )
        )
        # Store allowed_tools in pool for llm_decide to read
        try:
            await self.pool.remove("allowed-tools")
        except KeyError:
            pass
        await self.pool.add(
            ContextItem(
                id="allowed-tools",
                description=f"Tool filter for {persona.name} persona",
                content=set(persona.allowed_tools),
            )
        )
        self._active_role = persona_name

    async def clear_role(self) -> None:
        try:
            await self.pool.remove("active-role")
        except KeyError:
            pass
        try:
            await self.pool.remove("allowed-tools")
        except KeyError:
            pass
        self._active_role = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_personas.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coder/agent/session.py tests/test_personas.py
git commit -m "refactor: update session to use new create_agent and store allowed_tools in pool"
```

---

### Task 6: Rewrite `repl.py` — concurrent agent + stdin reader

**Files:**
- Modify: `coder/cli/repl.py`

- [ ] **Step 1: Rewrite repl.py with concurrent execution**

```python
# coder/cli/repl.py
import asyncio
import sys

from pygents import ContextItem, Turn
from coder.cli.commands import is_slash_command, list_slash_commands, load_slash_command
from coder.agent.session import Session
from coder.shared.console import console


async def read_user_input() -> str | None:
    loop = asyncio.get_event_loop()
    try:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            return None
        return line.rstrip("\n")
    except (EOFError, KeyboardInterrupt):
        return None


BUILTIN_COMMANDS = {"/help", "/role", "/quit", "/exit", "/quiet", "/verbose"}


async def handle_input(session: Session, user_input: str) -> str | None:
    stripped = user_input.strip()
    cmd_word = stripped.split(None, 1)[0] if stripped else ""

    if stripped == "/help":
        commands = list_slash_commands(cwd=session.config.cwd)
        console.system("Built-in commands:")
        console.system("  /help          - Show this help")
        console.system(
            "  /role <name>   - Switch persona (scout, planner, worker, reviewer)"
        )
        console.system("  /role          - Clear active persona")
        console.system(
            "  /quiet         - Hide tool traces (show summary after each turn)"
        )
        console.system("  /verbose       - Show tool traces (default)")
        console.system("  /quit          - Exit")
        if commands:
            console.system("\nSlash commands:")
            for cmd in commands:
                console.system(f"  /{cmd}")
        return None
    if cmd_word == "/role":
        parts = user_input.strip().split(None, 1)
        if len(parts) == 1:
            await session.clear_role()
            console.system("Cleared active role.")
        else:
            role_name = parts[1].strip()
            try:
                await session.switch_role(role_name)
                console.system(f"Switched to {role_name} role.")
            except KeyError:
                console.error(
                    f"Unknown role: {role_name}. Available: scout, planner, worker, reviewer"
                )
        return None
    if stripped in ("/quiet", "/verbose"):
        old = console.verbosity
        new = "quiet" if old == "normal" else "normal"
        console.set_verbosity(new)
        label = "Tool traces hidden." if new == "quiet" else "Tool traces visible."
        console.system(f"Verbosity: {old} -> {new}. {label}")
        return None
    if stripped in ("/quit", "/exit"):
        return None
    if is_slash_command(user_input):
        expanded = load_slash_command(user_input, cwd=session.config.cwd)
        if expanded is None:
            commands = list_slash_commands(cwd=session.config.cwd)
            if commands:
                console.error(
                    f"Unknown command. Available: {', '.join('/' + c for c in commands)}"
                )
            else:
                console.error(f"Unknown command: {cmd_word}")
            return None
        return expanded
    return user_input


async def run_agent(session: Session) -> None:
    """Consume agent.run() and print streamed text from llm_respond."""
    async for turn, value in session.agent.run():
        if isinstance(value, str):
            sys.stdout.write(value)
            sys.stdout.flush()


async def read_steering(session: Session, stop_event: asyncio.Event) -> None:
    """Background task: read stdin and push messages into steering queue.

    Uses a polling approach with stop_event so the task can be cancelled
    cleanly when the agent finishes (stdin.readline in executor is not
    cancellable, so we check stop_event between reads).
    """
    loop = asyncio.get_event_loop()
    while not stop_event.is_set():
        try:
            # Use a short timeout so we can check stop_event periodically
            line = await asyncio.wait_for(
                loop.run_in_executor(None, sys.stdin.readline),
                timeout=0.5,
            )
            if not line:
                break
            text = line.rstrip("\n")
            if text.strip():
                await session.steering_queue.put(text)
        except asyncio.TimeoutError:
            continue
        except (EOFError, KeyboardInterrupt):
            break


async def main(cwd: str | None = None) -> None:
    session = Session()
    await session.start(cwd=cwd)
    console.system("coder ready. Type /help for commands, /quit to exit.\n")

    from coder.agent.llm.decide import llm_decide

    while True:
        try:
            sys.stdout.write(console.prompt())
            sys.stdout.flush()
            user_input = await read_user_input()
            if user_input is None or user_input.strip() in ("/quit", "/exit"):
                console.system("\nGoodbye.")
                break
            if not user_input.strip():
                continue
            message = await handle_input(session, user_input)
            if message is None:
                continue

            await session.cq.append(
                ContextItem(content={"role": "user", "content": message})
            )
            await session.agent.put(Turn(llm_decide))

            # Run agent + background steering reader concurrently
            stop_event = asyncio.Event()
            steering_task = asyncio.create_task(read_steering(session, stop_event))
            try:
                await run_agent(session)
            finally:
                stop_event.set()
                steering_task.cancel()
                try:
                    await steering_task
                except asyncio.CancelledError:
                    pass

            console.flush_tool_summary()
            console.system("")
        except KeyboardInterrupt:
            console.system("\n\nInterrupted. Type /quit to exit.")
            continue
```

- [ ] **Step 2: Run the full test suite to check for regressions**

Run: `uv run pytest -v`
Expected: PASS (or only test_llm_call.py failures, which we handle in the next task)

- [ ] **Step 3: Commit**

```bash
git add coder/cli/repl.py
git commit -m "refactor: rewrite REPL with agent.run() consumption and concurrent steering"
```

---

### Task 7: Delete `call.py` and update test_llm_call.py

**Files:**
- Delete: `coder/agent/llm/call.py`
- Modify: `tests/test_llm_call.py`

- [ ] **Step 1: Delete call.py**

```bash
git rm coder/agent/llm/call.py
```

- [ ] **Step 2: Rewrite test_llm_call.py to test prompt.py only**

The tests in `test_llm_call.py` test `build_system_prompt` and `build_messages` which live in `prompt.py`. Update the imports:

```python
# tests/test_llm_call.py — rename to tests/test_prompt.py or update imports
# The existing tests are for build_system_prompt and build_messages from prompt.py
# They should already work since prompt.py is unchanged.
# Just verify imports are correct:
from coder.agent.llm.prompt import build_system_prompt, build_messages
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_llm_call.py -v`
Expected: PASS

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove call.py, update test imports"
```

---

### Task 8: Update `__init__.py` and verify integration

**Files:**
- Modify: `coder/agent/tools/__init__.py`
- Modify: `coder/agent/llm/__init__.py` (create if needed)

- [ ] **Step 1: Verify tools/__init__.py is still correct**

The `ALL_TOOLS` list in `coder/agent/tools/__init__.py` should remain the same — it only lists file/shell tools. The llm tools are added in `loop.py`'s `create_agent()`. No changes needed here, just verify.

- [ ] **Step 2: Create llm/__init__.py if it doesn't exist**

```python
# coder/agent/llm/__init__.py
# (empty or minimal — just ensure the package is importable)
```

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 4: Manual smoke test**

Run: `uv run python main.py`

Test these scenarios:
1. Type a simple question — should get a streamed response
2. Type "read main.py" — should see tool_read execute, then a response
3. Type `/role scout` then a question — should use scout persona
4. Type `/role` to clear — should restore default
5. Type `/quit` — should exit cleanly

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: verify integration, add llm __init__"
```

---

### Task 9: Clean up — remove `allowed_tools` from Session dataclass

**Files:**
- Modify: `coder/agent/session.py`

- [ ] **Step 1: Verify `allowed_tools` field is no longer on Session**

The rewrite in Task 5 already removed `allowed_tools: set[str] | None = None` from the Session dataclass (it's now stored in the pool). Verify this is the case. If it's still there, remove it.

- [ ] **Step 2: Search for any remaining references to `session.allowed_tools`**

Run: `uv run grep -r "session.allowed_tools\|self.allowed_tools" coder/`
Expected: No results

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: clean up removed allowed_tools references"
```