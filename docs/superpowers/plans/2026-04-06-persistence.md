# Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three-tier memory (working, episodic, semantic) persisted as .md files in `~/.coder/memory/`, managed by middleware hooks.

**Architecture:** A new `coder/agent/memory/` module handles reading, writing, and decaying .md memory files. Three hooks integrate with the session lifecycle: startup (load semantic + decay episodic), after-turn (extract semantic facts), and compaction (save episodic entry). Slash commands `/remember`, `/forget`, `/memories`, `/recall` provide explicit overrides.

**Tech Stack:** Python 3.13, pydantic (for extraction schema), PyAIToolkit (for LLM calls), YAML frontmatter (via `yaml` — already a dependency), pygents hooks.

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `coder/agent/memory/__init__.py` | Package init |
| Create | `coder/agent/memory/store.py` | Read/write/delete .md files with YAML frontmatter, list entries, build index |
| Create | `coder/agent/memory/extraction.py` | LLM-based semantic fact extraction from conversation turns |
| Create | `coder/agent/memory/decay.py` | Age-based episodic memory summarization/merging |
| Create | `coder/agent/memory/prompts.py` | Prompt templates for extraction and decay |
| Modify | `coder/agent/session.py` | Call startup hook (load semantic memory, run decay) |
| Modify | `coder/agent/hooks.py` | Add after-turn semantic extraction hook |
| Modify | `coder/agent/tools/compact.py` | Add episodic write side effect after compaction |
| Modify | `coder/agent/llm/prompt.py` | Inject semantic memory into system prompt |
| Modify | `coder/cli/repl.py` | Handle `/remember`, `/forget`, `/memories`, `/recall` commands |
| Create | `tests/test_memory_store.py` | Tests for store.py |
| Create | `tests/test_memory_extraction.py` | Tests for extraction.py |
| Create | `tests/test_memory_decay.py` | Tests for decay.py |
| Create | `tests/test_memory_commands.py` | Tests for slash command handling |

---

### Task 1: Memory Store — File I/O Layer

**Files:**
- Create: `coder/agent/memory/__init__.py`
- Create: `coder/agent/memory/store.py`
- Create: `tests/test_memory_store.py`

This is the foundation — all other tasks depend on it. Handles reading/writing .md files with YAML frontmatter.

- [ ] **Step 1: Write failing tests for store.py**

```python
# tests/test_memory_store.py
import os
from datetime import datetime, timezone

from coder.agent.memory.store import (
    MemoryEntry,
    read_entry,
    write_entry,
    delete_entry,
    list_entries,
    build_memory_index,
)


def test_write_and_read_semantic(tmp_path):
    entry = MemoryEntry(
        type="semantic",
        topic="user-preferences",
        content="Prefers spaces over tabs.",
        tags=["preferences"],
    )
    write_entry(entry, base_dir=str(tmp_path))
    result = read_entry("semantic", "user-preferences", base_dir=str(tmp_path))
    assert result is not None
    assert result.content == "Prefers spaces over tabs."
    assert result.type == "semantic"
    assert result.topic == "user-preferences"
    assert "preferences" in result.tags
    assert result.created is not None
    assert result.updated is not None


def test_write_overwrites_existing(tmp_path):
    entry1 = MemoryEntry(
        type="semantic",
        topic="user-preferences",
        content="Prefers tabs.",
        tags=["preferences"],
    )
    write_entry(entry1, base_dir=str(tmp_path))
    first = read_entry("semantic", "user-preferences", base_dir=str(tmp_path))

    entry2 = MemoryEntry(
        type="semantic",
        topic="user-preferences",
        content="Prefers spaces.",
        tags=["preferences"],
    )
    write_entry(entry2, base_dir=str(tmp_path))
    second = read_entry("semantic", "user-preferences", base_dir=str(tmp_path))

    assert second.content == "Prefers spaces."
    assert second.created == first.created  # preserves original created
    assert second.updated >= first.updated


def test_write_and_read_episodic(tmp_path):
    entry = MemoryEntry(
        type="episodic",
        topic="2026-04-06T14-30-00",
        content="Refactored the auth module.",
        tags=[],
    )
    write_entry(entry, base_dir=str(tmp_path))
    result = read_entry("episodic", "2026-04-06T14-30-00", base_dir=str(tmp_path))
    assert result is not None
    assert result.content == "Refactored the auth module."


def test_delete_entry(tmp_path):
    entry = MemoryEntry(
        type="semantic",
        topic="to-delete",
        content="Temporary.",
        tags=[],
    )
    write_entry(entry, base_dir=str(tmp_path))
    assert read_entry("semantic", "to-delete", base_dir=str(tmp_path)) is not None
    deleted = delete_entry("semantic", "to-delete", base_dir=str(tmp_path))
    assert deleted is True
    assert read_entry("semantic", "to-delete", base_dir=str(tmp_path)) is None


def test_delete_nonexistent(tmp_path):
    deleted = delete_entry("semantic", "nope", base_dir=str(tmp_path))
    assert deleted is False


def test_list_entries(tmp_path):
    for i in range(3):
        write_entry(
            MemoryEntry(type="semantic", topic=f"topic-{i}", content=f"Fact {i}", tags=[]),
            base_dir=str(tmp_path),
        )
    entries = list_entries("semantic", base_dir=str(tmp_path))
    assert len(entries) == 3
    topics = {e.topic for e in entries}
    assert topics == {"topic-0", "topic-1", "topic-2"}


def test_list_entries_empty(tmp_path):
    entries = list_entries("semantic", base_dir=str(tmp_path))
    assert entries == []


def test_build_memory_index(tmp_path):
    write_entry(
        MemoryEntry(type="semantic", topic="prefs", content="Likes Python.", tags=["lang"]),
        base_dir=str(tmp_path),
    )
    write_entry(
        MemoryEntry(type="semantic", topic="tools", content="Uses pytest.", tags=["testing"]),
        base_dir=str(tmp_path),
    )
    index = build_memory_index(base_dir=str(tmp_path))
    assert "Likes Python." in index
    assert "Uses pytest." in index
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/mtts/Code/coder && python -m pytest tests/test_memory_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coder.agent.memory'`

- [ ] **Step 3: Create package init**

```python
# coder/agent/memory/__init__.py
```

Empty file — just makes it a package.

- [ ] **Step 4: Implement store.py**

```python
# coder/agent/memory/store.py
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import yaml


DEFAULT_MEMORY_DIR = os.path.expanduser("~/.coder/memory")


@dataclass
class MemoryEntry:
    type: str  # "semantic" or "episodic"
    topic: str  # filename stem (e.g. "user-preferences" or "2026-04-06T14-30-00")
    content: str  # markdown body
    tags: list[str] = field(default_factory=list)
    created: datetime | None = None
    updated: datetime | None = None
    decay: str | None = None  # "weekly" or "monthly" for merged episodic entries


def _entry_path(memory_type: str, topic: str, base_dir: str) -> str:
    return os.path.join(base_dir, memory_type, f"{topic}.md")


def write_entry(entry: MemoryEntry, base_dir: str = DEFAULT_MEMORY_DIR) -> None:
    path = _entry_path(entry.type, entry.topic, base_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    now = datetime.now(timezone.utc)

    # Preserve original created timestamp if file exists
    existing = read_entry(entry.type, entry.topic, base_dir)
    created = existing.created if existing else now
    updated = now

    frontmatter = {
        "type": entry.type,
        "created": created.isoformat(),
        "updated": updated.isoformat(),
        "tags": entry.tags,
    }
    if entry.decay:
        frontmatter["decay"] = entry.decay

    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(yaml.dump(frontmatter, default_flow_style=False))
        f.write("---\n\n")
        f.write(entry.content)
        f.write("\n")


def read_entry(
    memory_type: str, topic: str, base_dir: str = DEFAULT_MEMORY_DIR
) -> MemoryEntry | None:
    path = _entry_path(memory_type, topic, base_dir)
    if not os.path.isfile(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # Parse YAML frontmatter
    if not text.startswith("---"):
        return MemoryEntry(type=memory_type, topic=topic, content=text)

    parts = text.split("---", 2)
    if len(parts) < 3:
        return MemoryEntry(type=memory_type, topic=topic, content=text)

    meta = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()

    created = None
    if "created" in meta:
        created = datetime.fromisoformat(meta["created"])
    updated = None
    if "updated" in meta:
        updated = datetime.fromisoformat(meta["updated"])

    return MemoryEntry(
        type=meta.get("type", memory_type),
        topic=topic,
        content=body,
        tags=meta.get("tags", []),
        created=created,
        updated=updated,
        decay=meta.get("decay"),
    )


def delete_entry(
    memory_type: str, topic: str, base_dir: str = DEFAULT_MEMORY_DIR
) -> bool:
    path = _entry_path(memory_type, topic, base_dir)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def list_entries(
    memory_type: str, base_dir: str = DEFAULT_MEMORY_DIR
) -> list[MemoryEntry]:
    dir_path = os.path.join(base_dir, memory_type)
    if not os.path.isdir(dir_path):
        return []
    entries = []
    for name in sorted(os.listdir(dir_path)):
        if name.endswith(".md"):
            topic = name[:-3]
            entry = read_entry(memory_type, topic, base_dir)
            if entry:
                entries.append(entry)
    return entries


def build_memory_index(base_dir: str = DEFAULT_MEMORY_DIR) -> str:
    entries = list_entries("semantic", base_dir)
    if not entries:
        return ""
    parts = []
    for entry in entries:
        parts.append(f"### {entry.topic}\n{entry.content}")
    return "\n\n".join(parts)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/mtts/Code/coder && python -m pytest tests/test_memory_store.py -v`
Expected: All 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add coder/agent/memory/__init__.py coder/agent/memory/store.py tests/test_memory_store.py
git commit -m "feat: add memory store — file I/O layer for .md persistence"
```

---

### Task 2: Semantic Extraction — LLM-Based Fact Extraction

**Files:**
- Create: `coder/agent/memory/prompts.py`
- Create: `coder/agent/memory/extraction.py`
- Create: `tests/test_memory_extraction.py`

Depends on: Task 1

- [ ] **Step 1: Write failing tests for extraction**

```python
# tests/test_memory_extraction.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from coder.agent.memory.extraction import extract_semantic_facts, SemanticFact


@pytest.mark.asyncio
async def test_extract_returns_facts():
    toolkit = MagicMock()
    response = MagicMock()
    response.content = json.dumps([
        {"topic": "user-preferences", "content": "Prefers spaces over tabs."}
    ])
    toolkit.chat = AsyncMock(return_value=response)

    facts = await extract_semantic_facts(
        toolkit, "user: please use spaces not tabs", "", ""
    )
    assert len(facts) == 1
    assert facts[0].topic == "user-preferences"
    assert facts[0].content == "Prefers spaces over tabs."


@pytest.mark.asyncio
async def test_extract_returns_empty_on_nothing():
    toolkit = MagicMock()
    response = MagicMock()
    response.content = "nothing"
    toolkit.chat = AsyncMock(return_value=response)

    facts = await extract_semantic_facts(toolkit, "hello", "", "")
    assert facts == []


@pytest.mark.asyncio
async def test_extract_handles_malformed_json():
    toolkit = MagicMock()
    response = MagicMock()
    response.content = "not valid json at all"
    toolkit.chat = AsyncMock(return_value=response)

    facts = await extract_semantic_facts(toolkit, "hello", "", "")
    assert facts == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/mtts/Code/coder && python -m pytest tests/test_memory_extraction.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create prompts.py**

```python
# coder/agent/memory/prompts.py

EXTRACTION_SYSTEM_PROMPT = """You are a memory extraction assistant. You analyze conversation turns between a user and an AI coding assistant and extract durable facts worth remembering across sessions.

Focus on:
- User preferences (formatting, tools, coding style)
- Project conventions (naming, architecture, patterns)
- User role, expertise, and background
- Recurring project constraints

Do NOT extract:
- Ephemeral task details (what file is being edited right now)
- Information already in the existing memories
- Obvious facts derivable from the code itself"""

EXTRACTION_PROMPT = """## Existing Memories
{{ existing_memories }}

## Current Turn
{{ turn_content }}

## Current System Prompt Context
{{ system_context }}

Extract any user preferences, project facts, or conventions worth remembering long-term. Return a JSON array of objects with "topic" (slugified, e.g. "user-preferences") and "content" (the fact as a concise sentence or two). If a topic already exists in memories above, your content should merge old and new into a coherent replacement.

If there is nothing worth remembering, return exactly: nothing

Return ONLY the JSON array or "nothing". No other text."""

DECAY_SYSTEM_PROMPT = """You are a memory summarization assistant. You merge multiple session summaries into a single concise summary that preserves the most important information."""

DECAY_PROMPT = """Merge the following session summaries into a single concise summary. Preserve key decisions, important context, and significant events. Drop redundant details.

{{ entries }}

Return ONLY the merged summary as markdown text."""
```

- [ ] **Step 4: Implement extraction.py**

```python
# coder/agent/memory/extraction.py
import json
from dataclasses import dataclass

from coder.agent.memory.prompts import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_PROMPT


@dataclass
class SemanticFact:
    topic: str
    content: str


async def extract_semantic_facts(
    toolkit, turn_content: str, existing_memories: str, system_context: str
) -> list[SemanticFact]:
    response = await toolkit.chat(
        template=EXTRACTION_PROMPT,
        turn_content=turn_content,
        existing_memories=existing_memories or "(none)",
        system_context=system_context or "(none)",
        system=EXTRACTION_SYSTEM_PROMPT,
    )

    text = response.content.strip()
    if text.lower() == "nothing":
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    facts = []
    for item in data:
        if isinstance(item, dict) and "topic" in item and "content" in item:
            facts.append(SemanticFact(topic=item["topic"], content=item["content"]))
    return facts
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/mtts/Code/coder && python -m pytest tests/test_memory_extraction.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add coder/agent/memory/prompts.py coder/agent/memory/extraction.py tests/test_memory_extraction.py
git commit -m "feat: add semantic fact extraction via LLM"
```

---

### Task 3: Episodic Decay — Age-Based Summarization

**Files:**
- Create: `coder/agent/memory/decay.py`
- Create: `tests/test_memory_decay.py`

Depends on: Task 1

- [ ] **Step 1: Write failing tests for decay**

```python
# tests/test_memory_decay.py
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from coder.agent.memory.decay import group_by_age, run_decay
from coder.agent.memory.store import MemoryEntry, write_entry, list_entries


def test_group_by_age():
    now = datetime.now(timezone.utc)
    entries = [
        MemoryEntry(type="episodic", topic="recent", content="A", created=now - timedelta(days=1)),
        MemoryEntry(type="episodic", topic="weekly", content="B", created=now - timedelta(days=10)),
        MemoryEntry(type="episodic", topic="monthly", content="C", created=now - timedelta(days=40)),
    ]
    recent, to_weekly, to_monthly = group_by_age(entries, now=now)
    assert len(recent) == 1
    assert recent[0].topic == "recent"
    assert len(to_weekly) == 1
    assert to_weekly[0].topic == "weekly"
    assert len(to_monthly) == 1
    assert to_monthly[0].topic == "monthly"


def test_group_by_age_skips_already_decayed():
    now = datetime.now(timezone.utc)
    entries = [
        MemoryEntry(
            type="episodic", topic="week-2026-W10", content="Already merged",
            created=now - timedelta(days=15), decay="weekly",
        ),
    ]
    recent, to_weekly, to_monthly = group_by_age(entries, now=now)
    assert len(recent) == 0
    assert len(to_weekly) == 0
    assert len(to_monthly) == 0


@pytest.mark.asyncio
async def test_run_decay_merges_weekly(tmp_path):
    now = datetime.now(timezone.utc)
    for i in range(3):
        write_entry(
            MemoryEntry(
                type="episodic",
                topic=f"old-{i}",
                content=f"Session {i} summary.",
                created=now - timedelta(days=10 + i),
            ),
            base_dir=str(tmp_path),
        )

    toolkit = MagicMock()
    response = MagicMock()
    response.content = "Merged weekly summary."
    toolkit.chat = AsyncMock(return_value=response)

    await run_decay(toolkit, base_dir=str(tmp_path), now=now)

    entries = list_entries("episodic", base_dir=str(tmp_path))
    # Original 3 should be replaced by 1 weekly summary
    assert len(entries) == 1
    assert entries[0].decay == "weekly"
    assert entries[0].content == "Merged weekly summary."


@pytest.mark.asyncio
async def test_run_decay_no_entries(tmp_path):
    toolkit = MagicMock()
    # Should not raise
    await run_decay(toolkit, base_dir=str(tmp_path))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/mtts/Code/coder && python -m pytest tests/test_memory_decay.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement decay.py**

```python
# coder/agent/memory/decay.py
from datetime import datetime, timedelta, timezone

from coder.agent.memory.prompts import DECAY_SYSTEM_PROMPT, DECAY_PROMPT
from coder.agent.memory.store import (
    DEFAULT_MEMORY_DIR,
    MemoryEntry,
    delete_entry,
    list_entries,
    write_entry,
)


def group_by_age(
    entries: list[MemoryEntry], now: datetime | None = None
) -> tuple[list[MemoryEntry], list[MemoryEntry], list[MemoryEntry]]:
    if now is None:
        now = datetime.now(timezone.utc)

    recent: list[MemoryEntry] = []
    to_weekly: list[MemoryEntry] = []
    to_monthly: list[MemoryEntry] = []

    for entry in entries:
        # Skip already-decayed entries
        if entry.decay:
            continue

        created = entry.created or now
        age = now - created

        if age < timedelta(days=7):
            recent.append(entry)
        elif age < timedelta(days=30):
            to_weekly.append(entry)
        else:
            to_monthly.append(entry)

    return recent, to_weekly, to_monthly


def _week_key(dt: datetime) -> str:
    year, week, _ = dt.isocalendar()
    return f"week-{year}-W{week:02d}"


def _month_key(dt: datetime) -> str:
    return f"month-{dt.year}-{dt.month:02d}"


async def _merge_group(
    toolkit,
    entries: list[MemoryEntry],
    key_fn,
    decay_label: str,
    base_dir: str,
) -> None:
    if not entries:
        return

    # Group entries by their target key (week or month)
    groups: dict[str, list[MemoryEntry]] = {}
    for entry in entries:
        created = entry.created or datetime.now(timezone.utc)
        key = key_fn(created)
        groups.setdefault(key, []).append(entry)

    for key, group in groups.items():
        entries_text = "\n\n---\n\n".join(
            f"### {e.topic}\n{e.content}" for e in group
        )

        response = await toolkit.chat(
            template=DECAY_PROMPT,
            entries=entries_text,
            system=DECAY_SYSTEM_PROMPT,
        )

        write_entry(
            MemoryEntry(
                type="episodic",
                topic=key,
                content=response.content,
                tags=[],
                decay=decay_label,
            ),
            base_dir=base_dir,
        )

        for entry in group:
            delete_entry("episodic", entry.topic, base_dir)


async def run_decay(
    toolkit,
    base_dir: str = DEFAULT_MEMORY_DIR,
    now: datetime | None = None,
) -> None:
    entries = list_entries("episodic", base_dir)
    if not entries:
        return

    _, to_weekly, to_monthly = group_by_age(entries, now=now)

    await _merge_group(toolkit, to_weekly, _week_key, "weekly", base_dir)
    await _merge_group(toolkit, to_monthly, _month_key, "monthly", base_dir)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/mtts/Code/coder && python -m pytest tests/test_memory_decay.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add coder/agent/memory/decay.py tests/test_memory_decay.py
git commit -m "feat: add episodic memory decay with age-based summarization"
```

---

### Task 4: Startup Hook — Load Semantic Memory + Run Decay

**Files:**
- Modify: `coder/agent/session.py:62-102`
- Modify: `coder/agent/llm/prompt.py:72-96`

Depends on: Tasks 1, 3

- [ ] **Step 1: Write failing test for startup loading**

Add to `tests/test_memory_store.py`:

```python
# Append to tests/test_memory_store.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pygents import ContextPool

from coder.agent.memory.store import MemoryEntry, write_entry, build_memory_index


@pytest.mark.asyncio
async def test_startup_loads_semantic_into_pool(tmp_path):
    write_entry(
        MemoryEntry(type="semantic", topic="prefs", content="Likes Python.", tags=[]),
        base_dir=str(tmp_path),
    )
    index = build_memory_index(base_dir=str(tmp_path))
    pool = ContextPool()
    from pygents import ContextItem
    await pool.add(ContextItem(id="semantic-memory", description="Semantic memory", content=index))

    item = pool.get("semantic-memory")
    assert "Likes Python." in str(item.content)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/mtts/Code/coder && python -m pytest tests/test_memory_store.py::test_startup_loads_semantic_into_pool -v`
Expected: PASS (this tests the building block — the integration comes next)

- [ ] **Step 3: Add startup memory loading to session.py**

In `coder/agent/session.py`, add import at the top:

```python
from coder.agent.memory.store import DEFAULT_MEMORY_DIR, build_memory_index
```

In `Session.start()`, after the `append-prompt` block (after line 98) and before `set_session(self)`, add:

```python
        # Load semantic memory into context pool
        memory_index = build_memory_index()
        if memory_index:
            await self.pool.add(
                ContextItem(
                    id="semantic-memory",
                    description="Persistent semantic memory",
                    content=memory_index,
                )
            )
```

- [ ] **Step 4: Add decay call to session.py startup**

After the semantic memory loading block, add:

```python
        # Run episodic memory decay
        if self.toolkit:
            from coder.agent.memory.decay import run_decay

            await run_decay(self.toolkit)
```

- [ ] **Step 5: Inject semantic memory into system prompt**

In `coder/agent/llm/prompt.py`, in `build_system_prompt()`, after the `skills_item` block (after line 93) and before the `append_item` block, add:

```python
    memory_item = _pool_get(pool, "semantic-memory")
    if memory_item and str(memory_item.content).strip():
        parts.append(f"## What You Know\n{memory_item.content}")
```

- [ ] **Step 6: Add memory awareness to the default base prompt**

In `coder/agent/session.py`, append to `DEFAULT_BASE_PROMPT` (before the closing `"""`):

```
\n\nYou have persistent memory stored in ~/.coder/memory/.
- Semantic memories (facts, preferences, conventions) are loaded above under "What You Know".
- Episodic memories (past session summaries) exist on disk. The user can search them with /recall.
- You do not need to manage memory explicitly — it is handled automatically.
- If the user says /remember or /forget, acknowledge the action."""
```

- [ ] **Step 7: Run all tests**

Run: `cd /home/mtts/Code/coder && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add coder/agent/session.py coder/agent/llm/prompt.py tests/test_memory_store.py
git commit -m "feat: load semantic memory at startup, inject into system prompt"
```

---

### Task 5: After-Turn Hook — Semantic Extraction

**Files:**
- Modify: `coder/agent/hooks.py`
- Modify: `coder/agent/loop.py:31`

Depends on: Tasks 1, 2, 4

- [ ] **Step 1: Write failing test for the hook**

```python
# tests/test_memory_hooks.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pygents import Agent, ContextItem, ContextPool, ContextQueue, Turn

from coder.agent.hooks import extract_memories
from coder.agent.memory.store import read_entry


@pytest.mark.asyncio
async def test_extract_memories_writes_facts(tmp_path):
    agent = MagicMock(spec=Agent)
    agent.context_pool = ContextPool()
    await agent.context_pool.add(
        ContextItem(id="semantic-memory", description="Semantic memory", content="")
    )

    turn = MagicMock(spec=Turn)
    turn.tool = MagicMock()
    turn.tool.metadata = MagicMock()
    turn.tool.metadata.name = "llm_respond"
    turn.output = [
        ContextItem(content={"role": "assistant", "content": "Sure, I'll use spaces."})
    ]

    # Mock the context queue to have the user message
    agent.context_queue = ContextQueue()
    await agent.context_queue.append(
        ContextItem(content={"role": "user", "content": "always use spaces not tabs"})
    )

    import json
    mock_toolkit = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps([
        {"topic": "user-preferences", "content": "Prefers spaces over tabs."}
    ])
    mock_toolkit.chat = AsyncMock(return_value=mock_response)

    with patch("coder.agent.hooks.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.toolkit = mock_toolkit
        mock_session.config = MagicMock()
        mock_session.config.memory_dir = str(tmp_path)
        mock_get_session.return_value = mock_session

        await extract_memories(agent, turn)

    entry = read_entry("semantic", "user-preferences", base_dir=str(tmp_path))
    assert entry is not None
    assert entry.content == "Prefers spaces over tabs."


@pytest.mark.asyncio
async def test_extract_memories_skips_non_respond_tools(tmp_path):
    agent = MagicMock(spec=Agent)
    turn = MagicMock(spec=Turn)
    turn.tool = MagicMock()
    turn.tool.metadata = MagicMock()
    turn.tool.metadata.name = "tool_read"

    # Should return immediately without doing anything
    with patch("coder.agent.hooks.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.config = MagicMock()
        mock_session.config.memory_dir = str(tmp_path)
        mock_get_session.return_value = mock_session

        await extract_memories(agent, turn)

    # No files should be created
    from coder.agent.memory.store import list_entries
    assert list_entries("semantic", base_dir=str(tmp_path)) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/mtts/Code/coder && python -m pytest tests/test_memory_hooks.py -v`
Expected: FAIL — `ImportError: cannot import name 'extract_memories'`

- [ ] **Step 3: Add memory_dir to SessionConfig**

In `coder/config/loader.py`, add to `SessionConfig`:

```python
    memory_dir: str = os.path.expanduser("~/.coder/memory")
```

- [ ] **Step 4: Implement extract_memories hook in hooks.py**

Add to `coder/agent/hooks.py`:

```python
from coder.agent.memory.extraction import extract_semantic_facts
from coder.agent.memory.store import (
    MemoryEntry,
    build_memory_index,
    write_entry,
)
from coder.agent.state import get_session


async def extract_memories(agent: Agent, turn: Turn) -> None:
    """After-turn hook: extract semantic facts from llm_respond turns."""
    raw_name = turn.tool.metadata.name
    if raw_name != "llm_respond":
        return

    session = get_session()
    memory_dir = session.config.memory_dir

    # Get the latest user message and assistant response from the turn
    assistant_content = ""
    if isinstance(turn.output, list):
        for item in turn.output:
            if isinstance(item, ContextItem) and isinstance(item.content, dict):
                assistant_content = item.content.get("content", "")
                break

    # Get latest user message from the context queue
    user_content = ""
    for item in reversed(list(agent.context_queue.items)):
        if isinstance(item.content, dict) and item.content.get("role") == "user":
            user_content = item.content.get("content", "")
            break

    if not user_content and not assistant_content:
        return

    turn_content = f"User: {user_content}\nAssistant: {assistant_content}"
    existing_memories = build_memory_index(base_dir=memory_dir)

    facts = await extract_semantic_facts(
        session.toolkit, turn_content, existing_memories, ""
    )

    if not facts:
        return

    for fact in facts:
        write_entry(
            MemoryEntry(
                type="semantic",
                topic=fact.topic,
                content=fact.content,
                tags=[],
            ),
            base_dir=memory_dir,
        )

    # Update the semantic-memory pool item so current session sees changes
    updated_index = build_memory_index(base_dir=memory_dir)
    try:
        await agent.context_pool.remove("semantic-memory")
    except KeyError:
        pass
    await agent.context_pool.add(
        ContextItem(
            id="semantic-memory",
            description="Persistent semantic memory",
            content=updated_index,
        )
    )
```

- [ ] **Step 5: Register the hook in loop.py**

In `coder/agent/loop.py`, add import:

```python
from coder.agent.hooks import trace_tool, extract_memories
```

After `agent.after_turn(trace_tool)` (line 31), add:

```python
    agent.after_turn(extract_memories)
```

- [ ] **Step 6: Update session.py to use memory_dir from config**

In `coder/agent/session.py`, update the startup memory loading to use `self.config.memory_dir`:

```python
        memory_index = build_memory_index(base_dir=self.config.memory_dir)
```

And update the decay call:

```python
            await run_decay(self.toolkit, base_dir=self.config.memory_dir)
```

Update the import in session.py:

```python
from coder.agent.memory.store import build_memory_index
```

(Remove the `DEFAULT_MEMORY_DIR` import since we now use `config.memory_dir`.)

- [ ] **Step 7: Run all tests**

Run: `cd /home/mtts/Code/coder && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add coder/agent/hooks.py coder/agent/loop.py coder/config/loader.py coder/agent/session.py tests/test_memory_hooks.py
git commit -m "feat: add after-turn hook for semantic memory extraction"
```

---

### Task 6: Compaction Hook — Episodic Write Side Effect

**Files:**
- Modify: `coder/agent/tools/compact.py`

Depends on: Task 1

- [ ] **Step 1: Write failing test**

```python
# tests/test_memory_episodic.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pygents import ContextItem, ContextPool, ContextQueue

from coder.agent.memory.store import list_entries


@pytest.mark.asyncio
async def test_compact_saves_episodic_entry(tmp_path):
    from coder.agent.tools.compact import compact

    session = MagicMock()
    session.toolkit = MagicMock()
    session.config = MagicMock()
    session.config.keep_recent_tokens = 20000
    session.config.memory_dir = str(tmp_path)

    pool = ContextPool()
    cq = ContextQueue()
    # Add enough items for compaction to have old messages
    for i in range(10):
        await cq.append(ContextItem(content={"role": "user", "content": f"message {i} " + "x" * 500}))

    summary_text = "Summary of the conversation."

    with patch("coder.agent.tools.compact.get_session", return_value=session):
        with patch("coder.agent.tools.compact.run_compaction", new_callable=AsyncMock) as mock_compact:
            mock_compact.return_value = (summary_text, list(cq.items)[-3:])

            results = []
            async for item in compact(cq, pool):
                results.append(item)

    # Should have saved an episodic entry
    entries = list_entries("episodic", base_dir=str(tmp_path))
    assert len(entries) == 1
    assert entries[0].content == summary_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/mtts/Code/coder && python -m pytest tests/test_memory_episodic.py -v`
Expected: FAIL — episodic entry not saved (compact.py doesn't write it yet)

- [ ] **Step 3: Add episodic write to compact.py**

In `coder/agent/tools/compact.py`, add import:

```python
from datetime import datetime, timezone

from coder.agent.memory.store import MemoryEntry, write_entry
```

After `dbg("COMPACT", f"kept {len(recent)} recent items", "33")` (line 32) and before the yield, add:

```python
    # Save episodic memory entry
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    write_entry(
        MemoryEntry(
            type="episodic",
            topic=timestamp,
            content=summary,
            tags=[],
        ),
        base_dir=session.config.memory_dir,
    )
    dbg("COMPACT", f"saved episodic entry: {timestamp}", "32")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/mtts/Code/coder && python -m pytest tests/test_memory_episodic.py -v`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `cd /home/mtts/Code/coder && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add coder/agent/tools/compact.py tests/test_memory_episodic.py
git commit -m "feat: save episodic memory entry on compaction"
```

---

### Task 7: Slash Commands — /remember, /forget, /memories, /recall

**Files:**
- Modify: `coder/cli/repl.py:51-119`
- Create: `tests/test_memory_commands.py`

Depends on: Tasks 1, 4

- [ ] **Step 1: Write failing tests for commands**

```python
# tests/test_memory_commands.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pygents import ContextItem, ContextPool

from coder.agent.memory.store import MemoryEntry, write_entry, read_entry, list_entries


@pytest.mark.asyncio
async def test_handle_forget(tmp_path):
    write_entry(
        MemoryEntry(type="semantic", topic="old-fact", content="Old.", tags=[]),
        base_dir=str(tmp_path),
    )

    session = MagicMock()
    session.config = MagicMock()
    session.config.memory_dir = str(tmp_path)
    session.pool = ContextPool()
    await session.pool.add(
        ContextItem(id="semantic-memory", description="mem", content="Old.")
    )

    from coder.cli.repl import handle_input

    result = await handle_input(session, "/forget old-fact")
    assert result is None  # command handled internally
    assert read_entry("semantic", "old-fact", base_dir=str(tmp_path)) is None


@pytest.mark.asyncio
async def test_handle_memories(tmp_path):
    write_entry(
        MemoryEntry(type="semantic", topic="prefs", content="Likes Python.", tags=[]),
        base_dir=str(tmp_path),
    )

    session = MagicMock()
    session.config = MagicMock()
    session.config.memory_dir = str(tmp_path)

    from coder.cli.repl import handle_input

    result = await handle_input(session, "/memories")
    assert result is None  # command handled internally


@pytest.mark.asyncio
async def test_handle_remember(tmp_path):
    session = MagicMock()
    session.config = MagicMock()
    session.config.memory_dir = str(tmp_path)
    session.config.cwd = str(tmp_path)

    from coder.cli.repl import handle_input

    result = await handle_input(session, "/remember I prefer pytest over unittest")
    # /remember returns expanded text for the agent to process
    assert result is not None
    assert "remember" in result.lower() or "pytest" in result.lower()


@pytest.mark.asyncio
async def test_handle_recall(tmp_path):
    write_entry(
        MemoryEntry(type="episodic", topic="2026-04-01T10-00-00", content="Worked on auth module refactor.", tags=[]),
        base_dir=str(tmp_path),
    )

    session = MagicMock()
    session.config = MagicMock()
    session.config.memory_dir = str(tmp_path)

    from coder.cli.repl import handle_input

    result = await handle_input(session, "/recall auth")
    assert result is None  # command handled internally
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/mtts/Code/coder && python -m pytest tests/test_memory_commands.py -v`
Expected: FAIL — commands not recognized yet

- [ ] **Step 3: Add memory commands to repl.py**

In `coder/cli/repl.py`, add imports:

```python
from coder.agent.memory.store import (
    MemoryEntry,
    delete_entry,
    list_entries,
    build_memory_index,
    write_entry,
)
```

Update `BUILTIN_COMMANDS`:

```python
BUILTIN_COMMANDS = {"/help", "/role", "/quit", "/exit", "/quiet", "/verbose", "/debug", "/remember", "/forget", "/memories", "/recall"}
```

In `handle_input()`, before the `if stripped in ("/quit", "/exit"):` block, add:

```python
    if cmd_word == "/remember":
        parts = user_input.strip().split(None, 1)
        if len(parts) < 2:
            console.error("Usage: /remember <text>")
            return None
        text = parts[1]
        return f"The user explicitly asked to remember the following. Extract it as a semantic memory fact and acknowledge:\n{text}"

    if cmd_word == "/forget":
        parts = user_input.strip().split(None, 1)
        if len(parts) < 2:
            console.error("Usage: /forget <topic>")
            return None
        topic = parts[1].strip()
        deleted = delete_entry("semantic", topic, base_dir=session.config.memory_dir)
        if deleted:
            # Update pool
            updated_index = build_memory_index(base_dir=session.config.memory_dir)
            try:
                await session.pool.remove("semantic-memory")
            except KeyError:
                pass
            if updated_index:
                await session.pool.add(
                    ContextItem(
                        id="semantic-memory",
                        description="Persistent semantic memory",
                        content=updated_index,
                    )
                )
            console.success(f"Forgot: {topic}")
        else:
            console.error(f"No memory found for topic: {topic}")
        return None

    if stripped == "/memories":
        entries = list_entries("semantic", base_dir=session.config.memory_dir)
        if not entries:
            console.system("No semantic memories stored.")
        else:
            console.system(f"Semantic memories ({len(entries)}):")
            for entry in entries:
                updated = entry.updated.strftime("%Y-%m-%d") if entry.updated else "?"
                console.system(f"  {entry.topic} (updated: {updated})")
                # Show first line of content
                first_line = entry.content.split("\n")[0][:80]
                console.system(f"    {first_line}")
        return None

    if cmd_word == "/recall":
        parts = user_input.strip().split(None, 1)
        if len(parts) < 2:
            console.error("Usage: /recall <query>")
            return None
        query = parts[1].strip().lower()
        entries = list_entries("episodic", base_dir=session.config.memory_dir)
        matches = [e for e in entries if query in e.content.lower() or query in e.topic.lower()]
        if not matches:
            console.system(f"No episodic memories matching: {query}")
        else:
            console.system(f"Found {len(matches)} episodic memories:")
            for entry in matches:
                date = entry.created.strftime("%Y-%m-%d %H:%M") if entry.created else entry.topic
                console.system(f"\n--- {date} ---")
                console.system(entry.content[:500])
        return None
```

- [ ] **Step 4: Update /help output**

In `handle_input()`, in the `/help` block, add after the `/quit` line:

```python
        console.system("\nMemory commands:")
        console.system("  /remember <text>  - Save a fact to semantic memory")
        console.system("  /forget <topic>   - Delete a semantic memory entry")
        console.system("  /memories         - List all semantic memories")
        console.system("  /recall <query>   - Search episodic memories")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/mtts/Code/coder && python -m pytest tests/test_memory_commands.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Run all tests**

Run: `cd /home/mtts/Code/coder && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add coder/cli/repl.py tests/test_memory_commands.py
git commit -m "feat: add /remember, /forget, /memories, /recall commands"
```

---

### Task 8: Integration Smoke Test

**Files:**
- Modify: `tests/test_integration.py` (or create a new one if the existing test is unrelated)

Depends on: All previous tasks

- [ ] **Step 1: Read existing integration test**

Read `tests/test_integration.py` to understand the pattern.

- [ ] **Step 2: Write integration test**

```python
# tests/test_memory_integration.py
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from coder.agent.memory.store import (
    MemoryEntry,
    write_entry,
    read_entry,
    list_entries,
    build_memory_index,
)
from coder.agent.memory.extraction import extract_semantic_facts
from coder.agent.memory.decay import run_decay


@pytest.mark.asyncio
async def test_full_memory_lifecycle(tmp_path):
    """Test: write semantic → read → update → build index → write episodic → decay."""

    # 1. Write a semantic entry
    write_entry(
        MemoryEntry(type="semantic", topic="testing", content="Uses pytest.", tags=["tools"]),
        base_dir=str(tmp_path),
    )

    # 2. Read it back
    entry = read_entry("semantic", "testing", base_dir=str(tmp_path))
    assert entry.content == "Uses pytest."

    # 3. Update (overwrite)
    write_entry(
        MemoryEntry(type="semantic", topic="testing", content="Uses pytest with fixtures.", tags=["tools"]),
        base_dir=str(tmp_path),
    )
    entry = read_entry("semantic", "testing", base_dir=str(tmp_path))
    assert entry.content == "Uses pytest with fixtures."

    # 4. Build index
    index = build_memory_index(base_dir=str(tmp_path))
    assert "Uses pytest with fixtures." in index

    # 5. Write episodic entries
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    for i in range(3):
        write_entry(
            MemoryEntry(
                type="episodic",
                topic=f"session-{i}",
                content=f"Worked on feature {i}.",
                created=now - timedelta(days=15 + i),
            ),
            base_dir=str(tmp_path),
        )

    # 6. Run decay
    toolkit = MagicMock()
    response = MagicMock()
    response.content = "Merged: worked on features 0-2."
    toolkit.chat = AsyncMock(return_value=response)

    await run_decay(toolkit, base_dir=str(tmp_path), now=now)

    # 7. Verify decay result
    episodic = list_entries("episodic", base_dir=str(tmp_path))
    assert len(episodic) == 1
    assert episodic[0].decay == "weekly"
    assert "Merged" in episodic[0].content
```

- [ ] **Step 3: Run integration test**

Run: `cd /home/mtts/Code/coder && python -m pytest tests/test_memory_integration.py -v`
Expected: PASS

- [ ] **Step 4: Run full test suite**

Run: `cd /home/mtts/Code/coder && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_memory_integration.py
git commit -m "test: add memory system integration test"
```
