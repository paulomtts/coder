# Architecture Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the flat `coder/` package into a feature-based architecture with `agent/`, `cli/`, `config/`, and `shared/` top-level modules, where LLM, compaction, personas, and tools are nested under `agent/`.

**Architecture:** Move from flat module layout to nested feature-based packages. The `agent/` package owns all agent internals (loop, session, LLM calls, compaction, personas, tools). `cli/` owns user interaction. `config/` owns bootstrapping. `shared/` owns cross-cutting constants. All imports throughout the codebase and tests are updated to match.

**Tech Stack:** Python 3.13+, pygents, py-ai-toolkit, pytest, pytest-asyncio

---

## File Structure

### Current layout (flat)

```
coder/
    __init__.py
    agent_loop.py
    cli.py
    compaction.py
    config.py
    constants.py
    llm_call.py
    personas.py
    prompts.py
    resources.py
    session.py
    tools/
        __init__.py
        read.py, write.py, edit.py, bash.py, grep.py, find.py, ls.py
```

### Target layout (feature-based)

```
coder/
    __init__.py
    agent/
        __init__.py              # re-exports: Session, create_agent, run_agent_loop
        loop.py                  # from agent_loop.py: run_agent_loop, register_all_tools, create_agent
        session.py               # from session.py: Session, DEFAULT_BASE_PROMPT
        llm/
            __init__.py          # re-exports: run_llm_call, build_system_prompt, AgentResponse
            call.py              # from llm_call.py: all LLM call logic
            prompt.py            # from llm_call.py: build_system_prompt, build_messages, build_tool_schemas, _build_guidelines, _build_tools_list
        compaction/
            __init__.py          # re-exports: run_compaction, should_compact, estimate_tokens
            summarizer.py        # from compaction.py: estimate_tokens, should_compact, split_messages, run_compaction
            prompts.py           # from compaction.py: all prompt constants (SUMMARIZATION_*, BRANCH_*)
        personas/
            __init__.py          # re-exports: PERSONAS, get_persona, get_allowed_tools, Persona
            definitions.py       # from personas.py: Persona, PERSONAS, prompt constants, get_persona, get_allowed_tools
        tools/
            __init__.py          # re-exports: _ALL_TOOLS list
            read.py              # unchanged
            write.py             # unchanged
            edit.py              # unchanged
            bash.py              # unchanged
            grep.py              # unchanged
            find.py              # unchanged
            ls.py                # unchanged
    cli/
        __init__.py              # re-exports: main
        repl.py                  # from cli.py: main, read_user_input, handle_input
        commands.py              # from prompts.py: is_slash_command, load_slash_command, list_slash_commands
    config/
        __init__.py              # re-exports: SessionConfig, load_config
        loader.py                # from config.py: SessionConfig, load_config
        resources.py             # from resources.py: discover_project_context, load_system_prompt_override, load_append_prompt
    shared/
        __init__.py              # re-exports: all constants
        constants.py             # from constants.py: unchanged
```

### Import mapping (old -> new)

| Old import | New import |
|---|---|
| `coder.agent_loop.run_agent_loop` | `coder.agent.loop.run_agent_loop` |
| `coder.agent_loop.create_agent` | `coder.agent.loop.create_agent` |
| `coder.agent_loop.register_all_tools` | `coder.agent.loop.register_all_tools` |
| `coder.session.Session` | `coder.agent.session.Session` |
| `coder.llm_call.run_llm_call` | `coder.agent.llm.call.run_llm_call` |
| `coder.llm_call.build_system_prompt` | `coder.agent.llm.prompt.build_system_prompt` |
| `coder.llm_call.build_messages` | `coder.agent.llm.prompt.build_messages` |
| `coder.llm_call.build_tool_schemas` | `coder.agent.llm.prompt.build_tool_schemas` |
| `coder.llm_call.AgentResponse` | `coder.agent.llm.call.AgentResponse` |
| `coder.llm_call.ToolCallRequest` | `coder.agent.llm.call.ToolCallRequest` |
| `coder.llm_call.execute_tool` | `coder.agent.llm.call.execute_tool` |
| `coder.compaction.*` | `coder.agent.compaction.summarizer.*` or `coder.agent.compaction.prompts.*` |
| `coder.personas.*` | `coder.agent.personas.definitions.*` |
| `coder.cli.main` | `coder.cli.repl.main` |
| `coder.prompts.*` | `coder.cli.commands.*` |
| `coder.config.*` | `coder.config.loader.*` |
| `coder.resources.*` | `coder.config.resources.*` |
| `coder.constants.*` | `coder.shared.constants.*` |
| `coder.tools.*` | `coder.agent.tools.*` |

---

### Task 1: Document the architecture in CLAUDE.md

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Write the CLAUDE.md file**

```markdown
# Coder

A Python coding agent harness inspired by [pi-mono](https://github.com/badlogic/pi-mono/).

## Architecture

Feature-based package layout. The `agent/` package owns all agent internals;
`cli/` owns user interaction; `config/` owns bootstrapping; `shared/` owns
cross-cutting constants.

```
coder/
    agent/                       # Core agent orchestration
        loop.py                  # Two-loop agent execution (inner LLM+tool, outer steering)
        session.py               # Session lifecycle, context pool, role switching, compaction
        llm/                     # LLM integration boundary
            call.py              # Streaming LLM call loop + tool dispatch
            prompt.py            # System prompt assembly, guidelines, tool schemas
        compaction/              # Context window management
            summarizer.py        # Token estimation, split logic, LLM-based summarization
            prompts.py           # All compaction/summarization prompt templates
        personas/                # Persona system
            definitions.py       # Persona dataclass, PERSONAS dict, prompt constants
        tools/                   # Tool implementations (pygents @tool decorators)
            read.py, write.py, edit.py, bash.py, grep.py, find.py, ls.py
    cli/                         # User interface
        repl.py                  # Interactive REPL loop, input handling
        commands.py              # Slash command loading & discovery
    config/                      # Configuration & resource loading
        loader.py                # .env, YAML, env var config loading
        resources.py             # AGENTS.md / CLAUDE.md project context discovery
    shared/                      # Cross-cutting utilities
        constants.py             # Output limits, defaults (MAX_LINES, MAX_BYTES, etc.)
```

## Dependencies

- `pygents` — async agent orchestration (ContextQueue, ContextPool, ToolRegistry, Agent)
- `py-ai-toolkit` — LLM calls (PyAIToolkit, LLMConfig, asend/chat)

## Running

```bash
uv run python main.py
```

## Testing

```bash
uv run pytest
```

## Key conventions

- All tools are async pygents `@tool()` functions in `coder/agent/tools/`
- Tools import constants from `coder.shared.constants`
- The session orchestrates everything: prompt assembly, compaction, role switching
- System prompt is assembled from layered sources (base, role, project context, append)
- Config loads from `.env` -> env vars -> `.coder/config.yaml` (later overrides earlier)
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md with architecture reference"
```

---

### Task 2: Create the `shared/` package (leaf dependency — no internal imports)

**Files:**
- Create: `coder/shared/__init__.py`
- Create: `coder/shared/constants.py`
- Modify: `tests/test_config.py` (import path)

- [ ] **Step 1: Create `coder/shared/__init__.py`**

```python
from coder.shared.constants import (
    MAX_LINES, MAX_BYTES, GREP_MAX_MATCHES, FIND_MAX_RESULTS,
    LS_MAX_ENTRIES, GREP_MAX_LINE_LENGTH, DEFAULT_HISTORY_LIMIT,
    DEFAULT_COMPACTION_THRESHOLD, DEFAULT_KEEP_RECENT_TOKENS, DEFAULT_TURN_TIMEOUT,
)
```

- [ ] **Step 2: Create `coder/shared/constants.py`**

Copy the contents of `coder/constants.py` exactly:

```python
# coder/shared/constants.py

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

- [ ] **Step 3: Make `coder/constants.py` a re-export shim**

Replace contents of `coder/constants.py` with:

```python
# Backwards-compatible re-export — all constants now live in coder.shared.constants
from coder.shared.constants import *  # noqa: F401,F403
```

This lets all existing imports (`from coder.constants import ...`) keep working while we migrate them one module at a time.

- [ ] **Step 4: Run tests to verify nothing broke**

Run: `uv run pytest -x -q`
Expected: All tests pass (constants are re-exported so all existing imports still work).

- [ ] **Step 5: Commit**

```bash
git add coder/shared/ coder/constants.py
git commit -m "refactor: extract shared/constants package with re-export shim"
```

---

### Task 3: Create the `config/` package

**Files:**
- Create: `coder/config/__init__.py`
- Create: `coder/config/loader.py`
- Create: `coder/config/resources.py`
- Modify: `coder/config.py` (re-export shim)
- Modify: `coder/resources.py` (re-export shim)

- [ ] **Step 1: Create `coder/config/__init__.py`**

```python
from coder.config.loader import SessionConfig, load_config
from coder.config.resources import discover_project_context, load_system_prompt_override, load_append_prompt
```

**IMPORTANT:** Python will have a naming conflict — `coder/config.py` and `coder/config/` cannot coexist. We must **rename** the old `coder/config.py` to something like `coder/_config_compat.py` first, then create the package, then make the compat file import from the package. Actually, the simplest approach: **delete `coder/config.py` and `coder/resources.py` after creating the package, since the `__init__.py` re-exports make `from coder.config import SessionConfig` work identically.**

Revised approach:

- [ ] **Step 1: Create `coder/config/` package directory with `loader.py` and `resources.py`**

Create `coder/config/loader.py` — copy from `coder/config.py` but update the constants import:

```python
# coder/config/loader.py
import os
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv

from coder.shared.constants import DEFAULT_COMPACTION_THRESHOLD, DEFAULT_HISTORY_LIMIT, DEFAULT_KEEP_RECENT_TOKENS

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
    target_cwd = cwd or os.getcwd()
    dotenv_path = os.path.join(target_cwd, ".env")
    load_dotenv(dotenv_path)

    config = SessionConfig.from_env()
    config.cwd = target_cwd
    config_path = os.path.join(config.cwd, ".coder", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}
        if "history_limit" in data: config.history_limit = data["history_limit"]
        if "compaction_threshold" in data: config.compaction_threshold = data["compaction_threshold"]
        if "keep_recent_tokens" in data: config.keep_recent_tokens = data["keep_recent_tokens"]
        if "model" in data: config.model = data["model"]
        if "api_key" in data: config.api_key = data["api_key"]
        if "base_url" in data: config.base_url = data["base_url"]
    return config
```

Create `coder/config/resources.py` — copy from `coder/resources.py` unchanged:

```python
# coder/config/resources.py
import os

CONTEXT_FILES = ["AGENTS.md", "CLAUDE.md"]

def discover_project_context(cwd: str) -> str:
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
    path = os.path.join(cwd, ".coder", "SYSTEM.md")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None

def load_append_prompt(cwd: str) -> str | None:
    path = os.path.join(cwd, ".coder", "APPEND_SYSTEM.md")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None
```

Create `coder/config/__init__.py`:

```python
from coder.config.loader import SessionConfig, load_config
from coder.config.resources import discover_project_context, load_system_prompt_override, load_append_prompt
```

- [ ] **Step 2: Delete old files and update test imports**

Delete `coder/config.py` and `coder/resources.py`.

Update `tests/test_config.py`:

```python
# tests/test_config.py
import os
import pytest
from coder.config.loader import SessionConfig, load_config

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
    assert config.history_limit == 50
```

Update `tests/test_resources.py`:

```python
# tests/test_resources.py
import os
import pytest
from coder.config.resources import discover_project_context, load_system_prompt_override, load_append_prompt

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

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_config.py tests/test_resources.py -x -v`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add coder/config/ tests/test_config.py tests/test_resources.py
git rm coder/config.py coder/resources.py
git commit -m "refactor: extract config/ package (loader + resources)"
```

---

### Task 4: Create the `agent/compaction/` package

**Files:**
- Create: `coder/agent/__init__.py` (empty for now, will grow)
- Create: `coder/agent/compaction/__init__.py`
- Create: `coder/agent/compaction/prompts.py`
- Create: `coder/agent/compaction/summarizer.py`
- Delete: `coder/compaction.py`
- Modify: `tests/test_compaction.py`

- [ ] **Step 1: Create directory structure and files**

Create `coder/agent/__init__.py`:

```python
```

Create `coder/agent/compaction/prompts.py` — the prompt constants from `coder/compaction.py`:

```python
SUMMARIZATION_SYSTEM_PROMPT = """You are a context summarization assistant. Your task is to read a conversation between a user and an AI coding assistant, then produce a structured summary following the exact format specified.\n\nDo NOT continue the conversation. Do NOT respond to any questions in the conversation. ONLY output the structured summary."""

SUMMARIZATION_PROMPT = """The messages above are a conversation to summarize. Create a structured context checkpoint summary that another LLM will use to continue the work.\n\nUse this EXACT format:\n\n## Goal\n[What is the user trying to accomplish? Can be multiple items if the session covers different tasks.]\n\n## Constraints & Preferences\n- [Any constraints, preferences, or requirements mentioned by user]\n- [Or "(none)" if none were mentioned]\n\n## Progress\n### Done\n- [x] [Completed tasks/changes]\n\n### In Progress\n- [ ] [Current work]\n\n### Blocked\n- [Issues preventing progress, if any]\n\n## Key Decisions\n- **[Decision]**: [Brief rationale]\n\n## Next Steps\n1. [Ordered list of what should happen next]\n\n## Critical Context\n- [Any data, examples, or references needed to continue]\n- [Or "(none)" if not applicable]\n\nKeep each section concise. Preserve exact file paths, function names, and error messages."""

UPDATE_SUMMARIZATION_PROMPT = """The messages above are NEW conversation messages to incorporate into the existing summary provided in <previous-summary> tags.\n\nUpdate the existing structured summary with new information. RULES:\n- PRESERVE all existing information from the previous summary\n- ADD new progress, decisions, and context from the new messages\n- UPDATE the Progress section: move items from "In Progress" to "Done" when completed\n- UPDATE "Next Steps" based on what was accomplished\n- PRESERVE exact file paths, function names, and error messages\n- If something is no longer relevant, you may remove it\n\nUse this EXACT format:\n\n## Goal\n[Preserve existing goals, add new ones if the task expanded]\n\n## Constraints & Preferences\n- [Preserve existing, add new ones discovered]\n\n## Progress\n### Done\n- [x] [Include previously done items AND newly completed items]\n\n### In Progress\n- [ ] [Current work - update based on progress]\n\n### Blocked\n- [Current blockers - remove if resolved]\n\n## Key Decisions\n- **[Decision]**: [Brief rationale] (preserve all previous, add new)\n\n## Next Steps\n1. [Update based on current state]\n\n## Critical Context\n- [Preserve important context, add new if needed]\n\nKeep each section concise. Preserve exact file paths, function names, and error messages."""

TURN_PREFIX_SUMMARIZATION_PROMPT = """This is the PREFIX of a turn that was too large to keep. The SUFFIX (recent work) is retained.\n\nSummarize the prefix to provide context for the retained suffix:\n\n## Original Request\n[What did the user ask for in this turn?]\n\n## Early Progress\n- [Key decisions and work done in the prefix]\n\n## Context for Suffix\n- [Information needed to understand the retained recent work]\n\nBe concise. Focus on what's needed to understand the kept suffix."""

BRANCH_SUMMARY_PROMPT = """Create a structured summary of this conversation branch for context when returning later.\n\nUse this EXACT format:\n\n## Goal\n[What was the user trying to accomplish in this branch?]\n\n## Constraints & Preferences\n- [Any constraints, preferences, or requirements mentioned]\n- [Or "(none)" if none were mentioned]\n\n## Progress\n### Done\n- [x] [Completed tasks/changes]\n\n### In Progress\n- [ ] [Work that was started but not finished]\n\n### Blocked\n- [Issues preventing progress, if any]\n\n## Key Decisions\n- **[Decision]**: [Brief rationale]\n\n## Next Steps\n1. [What should happen next to continue this work]\n\nKeep each section concise. Preserve exact file paths, function names, and error messages."""

BRANCH_SUMMARY_PREAMBLE = """The user explored a different conversation branch before returning here.\nSummary of that exploration:\n"""
```

Create `coder/agent/compaction/summarizer.py` — the logic functions:

```python
from pygents import ContextItem

from coder.agent.compaction.prompts import (
    SUMMARIZATION_PROMPT, SUMMARIZATION_SYSTEM_PROMPT, UPDATE_SUMMARIZATION_PROMPT,
)


def estimate_tokens(items: list[ContextItem]) -> int:
    total = 0
    for item in items:
        total += len(str(item.content)) // 4
    return total


def should_compact(items: list[ContextItem], threshold: float, max_context_tokens: int) -> bool:
    tokens = estimate_tokens(items)
    return tokens > threshold * max_context_tokens


def split_messages(items: list[ContextItem], keep_recent_tokens: int) -> tuple[list[ContextItem], list[ContextItem]]:
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


async def run_compaction(toolkit, items, existing_summary, keep_recent_tokens):
    old_messages, recent_messages = split_messages(items, keep_recent_tokens)
    if not old_messages:
        return existing_summary or "", recent_messages
    conversation = "\n".join(
        f"[{item.content.get('role', 'unknown')}]: {item.content.get('content', str(item.content))}"
        for item in old_messages if isinstance(item.content, dict)
    )
    if existing_summary:
        prompt_template = "<previous-summary>\n{{ previous_summary }}\n</previous-summary>\n\n{{ conversation }}\n\n{{ update_prompt }}"
        response = await toolkit.chat(template=prompt_template, previous_summary=existing_summary, conversation=conversation, update_prompt=UPDATE_SUMMARIZATION_PROMPT, system=SUMMARIZATION_SYSTEM_PROMPT)
    else:
        prompt_template = "{{ conversation }}\n\n{{ summarize_prompt }}"
        response = await toolkit.chat(template=prompt_template, conversation=conversation, summarize_prompt=SUMMARIZATION_PROMPT, system=SUMMARIZATION_SYSTEM_PROMPT)
    return response.content, recent_messages
```

Create `coder/agent/compaction/__init__.py`:

```python
from coder.agent.compaction.summarizer import estimate_tokens, should_compact, split_messages, run_compaction
from coder.agent.compaction.prompts import (
    SUMMARIZATION_SYSTEM_PROMPT, SUMMARIZATION_PROMPT, UPDATE_SUMMARIZATION_PROMPT,
    TURN_PREFIX_SUMMARIZATION_PROMPT, BRANCH_SUMMARY_PROMPT, BRANCH_SUMMARY_PREAMBLE,
)
```

- [ ] **Step 2: Delete old file and update test**

Delete `coder/compaction.py`.

Update `tests/test_compaction.py`:

```python
import pytest
from pygents import ContextItem
from coder.agent.compaction.summarizer import estimate_tokens, should_compact, split_messages
from coder.agent.compaction.prompts import (
    SUMMARIZATION_PROMPT, SUMMARIZATION_SYSTEM_PROMPT, UPDATE_SUMMARIZATION_PROMPT,
)

def test_estimate_tokens():
    items = [ContextItem(content={"role": "user", "content": "hello world"})]
    tokens = estimate_tokens(items)
    assert tokens > 0
    assert tokens == len(str({"role": "user", "content": "hello world"})) // 4

def test_should_compact_under_threshold():
    items = [ContextItem(content={"role": "user", "content": "short"})]
    assert not should_compact(items, threshold=0.8, max_context_tokens=100000)

def test_should_compact_over_threshold():
    big_content = "x" * 400000
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

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_compaction.py -x -v`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add coder/agent/ tests/test_compaction.py
git rm coder/compaction.py
git commit -m "refactor: extract agent/compaction/ package"
```

---

### Task 5: Create the `agent/personas/` package

**Files:**
- Create: `coder/agent/personas/__init__.py`
- Create: `coder/agent/personas/definitions.py`
- Delete: `coder/personas.py`
- Modify: `tests/test_personas.py`

- [ ] **Step 1: Create the package files**

Create `coder/agent/personas/definitions.py` — copy from `coder/personas.py` unchanged:

```python
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
1. `path/to/file` (lines 10-50) - Description

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
    "scout": Persona(name="scout", system_prompt=SCOUT_PROMPT, model_hint="haiku", allowed_tools=READ_ONLY_TOOLS),
    "planner": Persona(name="planner", system_prompt=PLANNER_PROMPT, model_hint="sonnet", allowed_tools=READ_ONLY_TOOLS),
    "worker": Persona(name="worker", system_prompt=WORKER_PROMPT, model_hint="sonnet", allowed_tools=ALL_TOOLS),
    "reviewer": Persona(name="reviewer", system_prompt=REVIEWER_PROMPT, model_hint="sonnet", allowed_tools=READ_ONLY_TOOLS),
}


def get_persona(name: str) -> Persona:
    return PERSONAS[name]


def get_allowed_tools(name: str) -> frozenset[str]:
    return PERSONAS[name].allowed_tools
```

Create `coder/agent/personas/__init__.py`:

```python
from coder.agent.personas.definitions import Persona, PERSONAS, get_persona, get_allowed_tools
```

- [ ] **Step 2: Delete old file and update test**

Delete `coder/personas.py`.

Update `tests/test_personas.py`:

```python
import pytest
from coder.agent.personas.definitions import PERSONAS, get_persona, get_allowed_tools


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


def test_reviewer_no_write_tools():
    tools = get_allowed_tools("reviewer")
    assert "tool_write" not in tools
    assert "tool_edit" not in tools
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_personas.py -x -v`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add coder/agent/personas/ tests/test_personas.py
git rm coder/personas.py
git commit -m "refactor: extract agent/personas/ package"
```

---

### Task 6: Move tools into `agent/tools/`

**Files:**
- Create: `coder/agent/tools/__init__.py`
- Move: `coder/tools/*.py` -> `coder/agent/tools/*.py`
- Delete: `coder/tools/`
- Modify: all tool test files (import paths)

- [ ] **Step 1: Create `coder/agent/tools/` and move files**

Copy all files from `coder/tools/` to `coder/agent/tools/`.

Update constants imports in each tool file — change `from coder.constants import ...` to `from coder.shared.constants import ...`:

Files to update:
- `coder/agent/tools/read.py`: `from coder.shared.constants import MAX_BYTES, MAX_LINES`
- `coder/agent/tools/bash.py`: `from coder.shared.constants import MAX_BYTES, MAX_LINES`
- `coder/agent/tools/grep.py`: `from coder.shared.constants import GREP_MAX_LINE_LENGTH, GREP_MAX_MATCHES, MAX_BYTES`
- `coder/agent/tools/find.py`: `from coder.shared.constants import FIND_MAX_RESULTS, MAX_BYTES`
- `coder/agent/tools/ls.py`: `from coder.shared.constants import LS_MAX_ENTRIES, MAX_BYTES`

`coder/agent/tools/write.py` and `coder/agent/tools/edit.py` don't import constants — copy unchanged.

Create `coder/agent/tools/__init__.py`:

```python
from coder.agent.tools.read import tool_read
from coder.agent.tools.write import tool_write
from coder.agent.tools.edit import tool_edit
from coder.agent.tools.bash import tool_bash
from coder.agent.tools.grep import tool_grep
from coder.agent.tools.find import tool_find
from coder.agent.tools.ls import tool_ls

ALL_TOOLS = [tool_read, tool_write, tool_edit, tool_bash, tool_grep, tool_find, tool_ls]
```

- [ ] **Step 2: Delete old `coder/tools/` directory**

Remove `coder/tools/` entirely.

- [ ] **Step 3: Update test imports**

Update each test file's import line:

- `tests/test_tools_read.py`: `from coder.agent.tools.read import tool_read`
- `tests/test_tools_write.py`: `from coder.agent.tools.write import tool_write`
- `tests/test_tools_edit.py`: `from coder.agent.tools.edit import tool_edit`
- `tests/test_tools_bash.py`: `from coder.agent.tools.bash import tool_bash`
- `tests/test_tools_grep.py`: `from coder.agent.tools.grep import tool_grep`
- `tests/test_tools_find.py`: `from coder.agent.tools.find import tool_find`
- `tests/test_tools_ls.py`: `from coder.agent.tools.ls import tool_ls`

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_tools_*.py -x -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add coder/agent/tools/ tests/test_tools_*.py
git rm -r coder/tools/
git commit -m "refactor: move tools/ into agent/tools/"
```

---

### Task 7: Create `agent/llm/` package (split `llm_call.py`)

**Files:**
- Create: `coder/agent/llm/__init__.py`
- Create: `coder/agent/llm/prompt.py`
- Create: `coder/agent/llm/call.py`
- Delete: `coder/llm_call.py`
- Modify: `tests/test_llm_call.py`

- [ ] **Step 1: Create `coder/agent/llm/prompt.py`**

This gets the prompt-building functions from `llm_call.py`:

```python
from typing import Any
from pygents import ContextPool, ContextQueue
from pygents.registry import ToolRegistry

LLM_VISIBLE_TOOLS = {"tool_read", "tool_write", "tool_edit", "tool_bash", "tool_grep", "tool_find", "tool_ls"}
GUIDELINE_BASH_ONLY = "Use bash for file operations like ls, rg, find"
GUIDELINE_PREFER_TOOLS = "Prefer grep/find/ls tools over bash for file exploration (faster, respects .gitignore)"
GUIDELINE_CONCISE = "Be concise in your responses"
GUIDELINE_FILE_PATHS = "Show file paths clearly when working with files"

def _build_guidelines(allowed_tools: set[str] | None) -> str:
    tools = allowed_tools or LLM_VISIBLE_TOOLS
    guidelines = []
    has_bash = "tool_bash" in tools
    has_search_tools = "tool_grep" in tools or "tool_find" in tools or "tool_ls" in tools
    if has_bash and has_search_tools:
        guidelines.append(GUIDELINE_PREFER_TOOLS)
    elif has_bash:
        guidelines.append(GUIDELINE_BASH_ONLY)
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
    tools = allowed_tools or LLM_VISIBLE_TOOLS
    snippets = {
        "tool_read": "read: Read file contents",
        "tool_write": "write: Create or overwrite files",
        "tool_edit": "edit: Make precise file edits with exact text replacement",
        "tool_bash": "bash: Execute bash commands",
        "tool_grep": "grep: Search file contents for patterns (respects .gitignore)",
        "tool_find": "find: Find files by glob pattern (respects .gitignore)",
        "tool_ls": "ls: List directory contents",
    }
    return "\n".join(f"- {snippets[t]}" for t in sorted(tools) if t in snippets)

def build_system_prompt(pool: ContextPool, allowed_tools: set[str] | None, tools_list: str | None = None) -> str:
    parts: list[str] = []
    base_item = pool._items.get("base-prompt")
    if base_item:
        base = str(base_item.content)
        tl = tools_list or _build_tools_list(allowed_tools)
        guidelines = _build_guidelines(allowed_tools)
        base = base.replace("{tools_list}", tl)
        base = base.replace("{guidelines}", guidelines)
        parts.append(base)
    role_item = pool._items.get("active-role")
    if role_item:
        parts.append(str(role_item.content))
    ctx_item = pool._items.get("project-context")
    if ctx_item and str(ctx_item.content).strip():
        parts.append(str(ctx_item.content))
    skills_item = pool._items.get("skills-index")
    if skills_item and str(skills_item.content).strip():
        parts.append(str(skills_item.content))
    append_item = pool._items.get("append-prompt")
    if append_item and str(append_item.content).strip():
        parts.append(str(append_item.content))
    return "\n\n".join(parts)

def build_messages(cq: ContextQueue, compaction_summary: str | None = None) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if compaction_summary:
        messages.append({"role": "system", "content": f"[Context from previous conversation]\n{compaction_summary}"})
    for item in cq.items:
        if isinstance(item.content, dict):
            messages.append(item.content)
    return messages

def build_tool_schemas(allowed_tools: set[str] | None) -> list[dict[str, Any]]:
    tools = allowed_tools or LLM_VISIBLE_TOOLS
    schemas = []
    for t in ToolRegistry.all():
        if t.__name__ not in tools:
            continue
        name = t.__name__[5:] if t.__name__.startswith("tool_") else t.__name__
        schema: dict[str, Any] = {"type": "function", "function": {"name": name, "description": t.metadata.description or ""}}
        if t.metadata.input_schema:
            schema["function"]["parameters"] = t.metadata.input_schema
        schemas.append(schema)
    return schemas
```

- [ ] **Step 2: Create `coder/agent/llm/call.py`**

This gets the LLM call loop, tool execution, models, and tool descriptions:

```python
import sys
from typing import Any
from pygents import ContextItem, ContextPool, ContextQueue
from pygents.registry import ToolRegistry
from pydantic import BaseModel, Field
from py_ai_toolkit import PyAIToolkit

from coder.agent.llm.prompt import build_system_prompt, LLM_VISIBLE_TOOLS

TOOL_NAME_MAP = {
    "read": "tool_read", "write": "tool_write", "edit": "tool_edit",
    "bash": "tool_bash", "grep": "tool_grep", "find": "tool_find", "ls": "tool_ls",
}


class ToolCallRequest(BaseModel):
    """A single tool call requested by the LLM."""
    name: str = Field(description="Tool name: read, write, edit, bash, grep, find, or ls")
    arguments: dict[str, Any] = Field(description="Arguments to pass to the tool")


class AgentResponse(BaseModel):
    """The LLM's response: either a text reply, or one or more tool calls to execute."""
    text: str | None = Field(None, description="Text response to the user. Set when no tools need to be called.")
    tool_calls: list[ToolCallRequest] | None = Field(None, description="Tools to call. Set when you need to use tools before responding.")


async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool by its LLM-facing name and return the result string."""
    pygents_name = TOOL_NAME_MAP.get(tool_name)
    if not pygents_name:
        return f"Error: unknown tool '{tool_name}'"

    try:
        tool_fn = ToolRegistry.get(pygents_name)
    except Exception:
        return f"Error: tool '{tool_name}' not registered"

    try:
        result = await tool_fn(**arguments)
        return str(result)
    except Exception as e:
        return f"Error executing {tool_name}: {e}"


def _build_tool_descriptions(allowed_tools: set[str] | None) -> str:
    """Build a human-readable tool reference for the system prompt."""
    tools = allowed_tools or LLM_VISIBLE_TOOLS
    descriptions = {
        "tool_read": "read(path, offset?, limit?) — Read file contents. Supports text and images. Output truncated to 2000 lines / 256KB. Use offset/limit for large files.",
        "tool_write": "write(path, content) — Write content to a file. Creates parent dirs. Use only for new files or complete rewrites.",
        "tool_edit": "edit(path, edits=[{old_text, new_text}]) — Exact text replacement. Each old_text must be unique in the file. All matches are against the original file.",
        "tool_bash": "bash(command, timeout?) — Execute a bash command. Returns stdout+stderr. Output truncated to 2000 lines / 256KB.",
        "tool_grep": "grep(pattern, path?, glob?, ignore_case?, literal?, context?, limit?) — Search file contents with ripgrep. Respects .gitignore.",
        "tool_find": "find(pattern, path?, limit?) — Find files by glob pattern with ripgrep. Respects .gitignore.",
        "tool_ls": "ls(path?, limit?) — List directory contents. Sorted alphabetically, '/' suffix for dirs.",
    }
    return "\n".join(f"- {descriptions[t]}" for t in sorted(tools) if t in descriptions)


async def run_llm_call(
    toolkit: PyAIToolkit,
    cq: ContextQueue,
    pool: ContextPool,
    allowed_tools: set[str] | None = None,
) -> None:
    """Run the LLM call loop with tool execution via asend().

    Uses py-ai-toolkit's asend() with a structured AgentResponse model.
    When the LLM requests tool calls, executes them and loops.
    When the LLM returns text, prints it and stops.

    Appends all messages (assistant + tool results) to cq.
    """
    system_prompt = build_system_prompt(pool, allowed_tools)
    tool_ref = _build_tool_descriptions(allowed_tools)

    compaction_summary = None
    try:
        summary_item = pool.get("compaction-summary")
        compaction_summary = str(summary_item.content)
    except KeyError:
        pass

    # Build the prompt with conversation history
    history_parts: list[str] = []

    if compaction_summary:
        history_parts.append(f"[Previous context]\n{compaction_summary}")

    for item in cq.items:
        if isinstance(item.content, dict):
            role = item.content.get("role", "unknown")
            content = item.content.get("content", "")
            if role == "tool":
                history_parts.append(f"[tool result]: {content}")
            elif content:
                history_parts.append(f"[{role}]: {content}")

    conversation = "\n\n".join(history_parts)

    iteration = 0
    max_iterations = 20  # safety limit

    while iteration < max_iterations:
        iteration += 1

        prompt = (
            "{{ system_prompt }}\n\n"
            "## Available Tools\n{{ tool_ref }}\n\n"
            "## Conversation\n{{ conversation }}"
        )

        response = await toolkit.asend(
            response_model=AgentResponse,
            template=prompt,
            system_prompt=system_prompt,
            tool_ref=tool_ref,
            conversation=conversation,
        )

        agent_response = response.content

        # If the LLM returned text, we're done
        if agent_response.text and not agent_response.tool_calls:
            print(agent_response.text)
            await cq.append(ContextItem(content={"role": "assistant", "content": agent_response.text}))
            return

        # Execute tool calls
        if agent_response.tool_calls:
            tool_results: list[str] = []
            for tc in agent_response.tool_calls:
                print(f"  [{tc.name}] ", end="", flush=True)
                result = await execute_tool(tc.name, tc.arguments)

                display = result[:200] + "..." if len(result) > 200 else result
                print(display.replace("\n", " "))

                tool_results.append(f"[tool result for {tc.name}]: {result}")

                # Append to cq
                await cq.append(ContextItem(content={
                    "role": "assistant",
                    "content": f"Called {tc.name}({tc.arguments})",
                }))
                await cq.append(ContextItem(content={
                    "role": "tool",
                    "content": result,
                }))

            # Append tool results to conversation for next iteration
            conversation += "\n\n" + "\n\n".join(tool_results)

        # If both text and tool_calls, print text and continue
        if agent_response.text:
            print(agent_response.text)
            conversation += f"\n\n[assistant]: {agent_response.text}"

        # If neither text nor tool_calls, something went wrong
        if not agent_response.text and not agent_response.tool_calls:
            print("[No response from LLM]")
            return
```

- [ ] **Step 3: Create `coder/agent/llm/__init__.py`**

```python
from coder.agent.llm.call import run_llm_call, execute_tool, AgentResponse, ToolCallRequest
from coder.agent.llm.prompt import build_system_prompt, build_messages, build_tool_schemas
```

- [ ] **Step 4: Delete old file and update test**

Delete `coder/llm_call.py`.

Update `tests/test_llm_call.py`:

```python
import pytest
from pygents import ContextItem, ContextPool, ContextQueue
from coder.agent.llm.prompt import build_system_prompt, build_messages

def test_build_system_prompt_basic():
    pool = ContextPool()
    pool._items["base-prompt"] = ContextItem(id="base-prompt", description="Base system prompt", content="You are a coding assistant.\n\nGuidelines:\n{guidelines}")
    prompt = build_system_prompt(pool, allowed_tools=None, tools_list="- read\n- bash")
    assert "coding assistant" in prompt
    assert "read" in prompt

def test_build_system_prompt_with_role():
    pool = ContextPool()
    pool._items["base-prompt"] = ContextItem(id="base-prompt", description="Base", content="Base prompt.\n\nGuidelines:\n{guidelines}")
    pool._items["active-role"] = ContextItem(id="active-role", description="Active role", content="You are a scout.")
    prompt = build_system_prompt(pool, allowed_tools=None, tools_list="- read")
    assert "scout" in prompt

def test_build_messages():
    cq = ContextQueue(limit=10)
    cq._items.append(ContextItem(content={"role": "user", "content": "hello"}))
    cq._items.append(ContextItem(content={"role": "assistant", "content": "hi there"}))
    messages = build_messages(cq)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

def test_build_messages_with_compaction_summary():
    cq = ContextQueue(limit=10)
    cq._items.append(ContextItem(content={"role": "user", "content": "hello"}))
    messages = build_messages(cq, compaction_summary="Previous work summary here.")
    assert len(messages) == 2
    assert "Previous work" in messages[0]["content"]
    assert messages[0]["role"] == "system"
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_llm_call.py -x -v`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add coder/agent/llm/ tests/test_llm_call.py
git rm coder/llm_call.py
git commit -m "refactor: extract agent/llm/ package (call + prompt)"
```

---

### Task 8: Create `agent/loop.py` and `agent/session.py`

**Files:**
- Create: `coder/agent/loop.py`
- Create: `coder/agent/session.py`
- Delete: `coder/agent_loop.py`
- Delete: `coder/session.py`
- Modify: `coder/agent/__init__.py`
- Modify: `tests/test_agent_loop.py`
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Create `coder/agent/loop.py`**

```python
import asyncio
from pygents import Agent, ContextItem, ContextPool, ContextQueue
from pygents.registry import ToolRegistry

from coder.agent.tools import ALL_TOOLS
from coder.agent.llm.call import run_llm_call


async def run_agent_loop(session) -> None:
    """Run the agent's main loop: call LLM, execute tools, repeat until done."""
    await session.check_compaction()

    while not session.steering_queue.empty():
        try:
            msg = session.steering_queue.get_nowait()
            await session.cq.append(
                ContextItem(content={"role": "user", "content": msg})
            )
        except asyncio.QueueEmpty:
            break

    await run_llm_call(
        toolkit=session.toolkit,
        cq=session.cq,
        pool=session.pool,
        allowed_tools=session.allowed_tools,
    )

def register_all_tools() -> list:
    for t in ALL_TOOLS:
        if ToolRegistry._registry.get(t.__name__) is None:
            ToolRegistry.register(t)
    return ALL_TOOLS

def create_agent(pool: ContextPool, cq: ContextQueue, steering_queue: asyncio.Queue | None = None) -> Agent:
    tools = register_all_tools()
    agent = Agent("coder", "A coding assistant", tools, context_pool=pool, context_queue=cq)
    if steering_queue is not None:
        @agent.before_turn
        async def inject_steering(agent: Agent) -> None:
            while not steering_queue.empty():
                try:
                    msg = steering_queue.get_nowait()
                    await agent.context_queue.append(ContextItem(content={"role": "user", "content": msg}))
                except asyncio.QueueEmpty:
                    break
    return agent
```

- [ ] **Step 2: Create `coder/agent/session.py`**

```python
import asyncio
from dataclasses import dataclass, field

from py_ai_toolkit import LLMConfig, PyAIToolkit
from pygents import Agent, ContextItem, ContextPool, ContextQueue

from coder.agent.loop import create_agent
from coder.agent.compaction import (
    BRANCH_SUMMARY_PREAMBLE, BRANCH_SUMMARY_PROMPT,
    estimate_tokens, run_compaction, should_compact,
)
from coder.config.loader import SessionConfig, load_config
from coder.agent.personas.definitions import get_persona
from coder.config.resources import discover_project_context, load_append_prompt, load_system_prompt_override

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
        self.config = load_config(cwd=cwd)
        llm_config = None
        if self.config.model or self.config.api_key:
            llm_config = LLMConfig(model=self.config.model, api_key=self.config.api_key, base_url=self.config.base_url or None)
        self.toolkit = PyAIToolkit(main_model_config=llm_config)
        self.cq = ContextQueue(limit=self.config.history_limit)
        self.pool = ContextPool()
        override = load_system_prompt_override(self.config.cwd)
        base_prompt = override if override else DEFAULT_BASE_PROMPT
        await self.pool.add(ContextItem(id="base-prompt", description="Base system prompt", content=base_prompt))
        project_ctx = discover_project_context(self.config.cwd)
        if project_ctx:
            await self.pool.add(ContextItem(id="project-context", description="Project context from AGENTS.md/CLAUDE.md", content=project_ctx))
        append = load_append_prompt(self.config.cwd)
        if append:
            await self.pool.add(ContextItem(id="append-prompt", description="Appended system prompt instructions", content=append))
        self.agent = create_agent(pool=self.pool, cq=self.cq, steering_queue=self.steering_queue)

    async def switch_role(self, persona_name: str) -> None:
        persona = get_persona(persona_name)
        if len(self.cq) > 0 and self.toolkit:
            conversation = "\n".join(
                f"[{item.content.get('role', '?')}]: {item.content.get('content', '')}"
                for item in self.cq.items if isinstance(item.content, dict)
            )
            response = await self.toolkit.chat(template="{{ conversation }}\n\n{{ prompt }}", conversation=conversation, prompt=BRANCH_SUMMARY_PROMPT)
            try: await self.pool.remove("branch-summary")
            except KeyError: pass
            await self.pool.add(ContextItem(id="branch-summary", description="Summary of previous conversation branch", content=BRANCH_SUMMARY_PREAMBLE + response.content))
        try: await self.pool.remove("active-role")
        except KeyError: pass
        await self.pool.add(ContextItem(id="active-role", description=f"Active role: {persona.name}", content=persona.system_prompt))
        self.allowed_tools = set(persona.allowed_tools)
        self._active_role = persona_name

    async def clear_role(self) -> None:
        try: await self.pool.remove("active-role")
        except KeyError: pass
        self.allowed_tools = None
        self._active_role = None

    async def check_compaction(self) -> None:
        if not self.toolkit:
            return
        items = self.cq.items
        max_tokens = 128000
        if not should_compact(items, self.config.compaction_threshold, max_tokens):
            return
        existing_summary = None
        try:
            summary_item = self.pool.get("compaction-summary")
            existing_summary = str(summary_item.content)
        except KeyError:
            pass
        summary, recent = await run_compaction(self.toolkit, items, existing_summary, self.config.keep_recent_tokens)
        try: await self.pool.remove("compaction-summary")
        except KeyError: pass
        await self.pool.add(ContextItem(id="compaction-summary", description="Compacted conversation summary", content=summary))
        await self.cq.clear()
        for item in recent:
            await self.cq.append(item)
```

- [ ] **Step 3: Update `coder/agent/__init__.py`**

```python
from coder.agent.session import Session
from coder.agent.loop import create_agent, run_agent_loop, register_all_tools
```

- [ ] **Step 4: Delete old files and update tests**

Delete `coder/agent_loop.py` and `coder/session.py`.

Update `tests/test_agent_loop.py`:

```python
import asyncio
import pytest
from pygents import ContextPool, ContextQueue
from coder.agent.loop import create_agent, register_all_tools

@pytest.mark.asyncio
async def test_register_all_tools():
    register_all_tools()
    from pygents.registry import ToolRegistry
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

Update `tests/test_integration.py`:

```python
# tests/test_integration.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pygents import ContextItem

from coder.agent.session import Session


@pytest.mark.asyncio
async def test_session_start(tmp_path):
    session = Session()
    with patch.dict("os.environ", {"LLM_MODEL": "test-model", "LLM_API_KEY": "test-key"}):
        await session.start(cwd=str(tmp_path))
    assert session.agent is not None
    assert session.agent.name == "coder"
    assert session.pool.get("base-prompt") is not None
    assert session.toolkit is not None


@pytest.mark.asyncio
async def test_session_with_project_context(tmp_path):
    (tmp_path / "AGENTS.md").write_text("Be helpful and concise.")
    session = Session()
    with patch.dict("os.environ", {"LLM_MODEL": "test-model", "LLM_API_KEY": "test-key"}):
        await session.start(cwd=str(tmp_path))
    ctx = session.pool.get("project-context")
    assert "Be helpful" in str(ctx.content)


@pytest.mark.asyncio
async def test_session_role_switching(tmp_path):
    session = Session()
    with patch.dict("os.environ", {"LLM_MODEL": "test-model", "LLM_API_KEY": "test-key"}):
        await session.start(cwd=str(tmp_path))
    session.toolkit.chat = AsyncMock(return_value=MagicMock(content="Branch summary"))
    await session.switch_role("scout")
    role = session.pool.get("active-role")
    assert "scout" in str(role.content).lower() or "investigate" in str(role.content).lower()
    assert session.allowed_tools is not None
    assert "tool_write" not in session.allowed_tools


@pytest.mark.asyncio
async def test_session_compaction(tmp_path):
    session = Session()
    with patch.dict("os.environ", {"LLM_MODEL": "test-model", "LLM_API_KEY": "test-key"}):
        await session.start(cwd=str(tmp_path))
    session.toolkit.chat = AsyncMock(return_value=MagicMock(content="## Goal\nTest goal"))
    for i in range(40):
        await session.cq.append(
            ContextItem(content={"role": "user", "content": f"Message {i} " + "x" * 5000})
        )
    session.config.compaction_threshold = 0.01
    await session.check_compaction()
    summary = session.pool.get("compaction-summary")
    assert "Goal" in str(summary.content)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_agent_loop.py tests/test_integration.py -x -v`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add coder/agent/loop.py coder/agent/session.py coder/agent/__init__.py tests/test_agent_loop.py tests/test_integration.py
git rm coder/agent_loop.py coder/session.py
git commit -m "refactor: extract agent/loop.py and agent/session.py"
```

---

### Task 9: Create the `cli/` package

**Files:**
- Create: `coder/cli/__init__.py`
- Create: `coder/cli/repl.py`
- Create: `coder/cli/commands.py`
- Delete: `coder/cli.py`
- Delete: `coder/prompts.py`
- Modify: `main.py`
- Modify: `tests/test_prompts.py`

- [ ] **Step 1: Create the package files**

**IMPORTANT:** Same naming conflict as `config` — `coder/cli.py` and `coder/cli/` cannot coexist. Delete the old file first.

Create `coder/cli/commands.py` — copy from `coder/prompts.py` unchanged:

```python
import os


def is_slash_command(text: str) -> bool:
    return bool(text) and text.startswith("/") and len(text) > 1


def load_slash_command(text: str, cwd: str) -> str | None:
    parts = text.split(None, 1)
    command = parts[0][1:]
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
    prompts_dir = os.path.join(cwd, ".coder", "prompts")
    if not os.path.isdir(prompts_dir):
        return []
    commands = []
    for name in sorted(os.listdir(prompts_dir)):
        if name.endswith(".md"):
            commands.append(name[:-3])
    return commands
```

Create `coder/cli/repl.py`:

```python
import asyncio
import sys

from pygents import ContextItem
from coder.cli.commands import is_slash_command, list_slash_commands, load_slash_command
from coder.agent.session import Session


async def read_user_input() -> str | None:
    loop = asyncio.get_event_loop()
    try:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            return None
        return line.rstrip("\n")
    except (EOFError, KeyboardInterrupt):
        return None


BUILTIN_COMMANDS = {"/help", "/role", "/quit", "/exit"}


async def handle_input(session: Session, user_input: str) -> str | None:
    stripped = user_input.strip()
    cmd_word = stripped.split(None, 1)[0] if stripped else ""

    if stripped == "/help":
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
    if cmd_word == "/role":
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
    if stripped in ("/quit", "/exit"):
        return None
    if is_slash_command(user_input):
        expanded = load_slash_command(user_input, cwd=session.config.cwd)
        if expanded is None:
            commands = list_slash_commands(cwd=session.config.cwd)
            if commands:
                print(f"Unknown command. Available: {', '.join('/' + c for c in commands)}")
            else:
                print(f"Unknown command: {cmd_word}")
            return None
        return expanded
    return user_input


async def main(cwd: str | None = None) -> None:
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
            await session.cq.append(ContextItem(content={"role": "user", "content": message}))
            from coder.agent.loop import run_agent_loop
            await run_agent_loop(session)
            print()
        except KeyboardInterrupt:
            print("\n\nInterrupted. Type /quit to exit.")
            continue
```

Create `coder/cli/__init__.py`:

```python
from coder.cli.repl import main
```

- [ ] **Step 2: Delete old files, update `main.py` and tests**

Delete `coder/cli.py` and `coder/prompts.py`.

Update `main.py`:

```python
# main.py
import asyncio

from coder.cli.repl import main

if __name__ == "__main__":
    asyncio.run(main())
```

Update `tests/test_prompts.py`:

```python
import os
import pytest
from coder.cli.commands import load_slash_command, list_slash_commands, is_slash_command

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

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_prompts.py -x -v`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add coder/cli/ main.py tests/test_prompts.py
git rm coder/cli.py coder/prompts.py
git commit -m "refactor: extract cli/ package (repl + commands)"
```

---

### Task 10: Clean up — remove old shim and empty `__init__.py`

**Files:**
- Delete: `coder/constants.py` (re-export shim no longer needed — all consumers now use `coder.shared.constants`)
- Modify: `coder/__init__.py`

- [ ] **Step 1: Verify no remaining imports of `coder.constants`**

Run: `grep -r "from coder.constants" coder/ tests/`
Expected: No matches (all were migrated in previous tasks).

If any remain, update them to `from coder.shared.constants import ...`.

- [ ] **Step 2: Delete the re-export shim**

Delete `coder/constants.py`.

- [ ] **Step 3: Update `coder/__init__.py`**

```python
```

(Keep it empty — the subpackages handle their own exports.)

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -x -v`
Expected: ALL tests pass. This is the final verification that the entire refactor is correct.

- [ ] **Step 5: Commit**

```bash
git rm coder/constants.py
git add coder/__init__.py
git commit -m "refactor: remove constants re-export shim, complete architecture refactor"
```

---

### Task 11: Update CLAUDE.md to reflect final state

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Verify the final directory structure matches the plan**

Run: `find coder/ -name "*.py" | sort`
Expected output:
```
coder/__init__.py
coder/agent/__init__.py
coder/agent/compaction/__init__.py
coder/agent/compaction/prompts.py
coder/agent/compaction/summarizer.py
coder/agent/llm/__init__.py
coder/agent/llm/call.py
coder/agent/llm/prompt.py
coder/agent/loop.py
coder/agent/personas/__init__.py
coder/agent/personas/definitions.py
coder/agent/session.py
coder/agent/tools/__init__.py
coder/agent/tools/bash.py
coder/agent/tools/edit.py
coder/agent/tools/find.py
coder/agent/tools/grep.py
coder/agent/tools/ls.py
coder/agent/tools/read.py
coder/agent/tools/write.py
coder/cli/__init__.py
coder/cli/commands.py
coder/cli/repl.py
coder/config/__init__.py
coder/config/loader.py
coder/config/resources.py
coder/shared/__init__.py
coder/shared/constants.py
```

- [ ] **Step 2: Update CLAUDE.md if any discrepancies**

If the structure matches, no changes needed — CLAUDE.md was written in Task 1 to reflect the target state.

- [ ] **Step 3: Run full test suite one final time**

Run: `uv run pytest -x -v`
Expected: ALL tests pass.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: finalize CLAUDE.md after architecture refactor"
```
