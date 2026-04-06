# Persistence via .md Files — Design Spec

## Overview

Add three-tier memory (working, episodic, semantic) to the coder agent, persisted as .md files in `~/.coder/memory/`. Memory is managed by middleware hooks — the LLM does not call memory tools directly.

- **Working memory** — the existing ContextPool/ContextQueue. In-memory, session-scoped. No changes needed.
- **Episodic memory** — records of what happened in past sessions. Created automatically during compaction. Decays over time via age-based summarization.
- **Semantic memory** — distilled knowledge about the user and project. Created by an after-turn hook that extracts facts via LLM. Overwritten on conflict (latest wins). Loaded into context pool at startup.

## File Structure

```
~/.coder/memory/
  semantic/          # one .md file per fact/topic
    user-preferences.md
    testing-conventions.md
    ...
  episodic/          # one .md file per compaction event or decay summary
    2026-04-06T14-30-00.md
    week-2026-W14.md
    month-2026-03.md
    ...
```

### File Format

All memory files use YAML frontmatter + markdown body:

```markdown
---
type: semantic
created: 2026-04-06T14:30:00
updated: 2026-04-06T16:45:12
tags: [preferences, formatting]
---

The user prefers spaces over tabs, 4-space indent.
They use pytest for all testing and prefer fixture-based setup.
```

- **Semantic files:** filename is a slugified topic (e.g., `user-preferences.md`). Has `updated` field in frontmatter.
- **Episodic files:** filename is an ISO timestamp for raw entries (e.g., `2026-04-06T14-30-00.md`), or a period identifier for decayed summaries (e.g., `week-2026-W14.md`, `month-2026-03.md`). Has a `decay` tag in frontmatter when merged.

## Hooks Architecture

### 1. Startup Hook

Runs once when a session begins (in `session.py`).

**Responsibilities:**

1. Read all files from `~/.coder/memory/semantic/`.
2. Concatenate their contents into a single context item.
3. Add it to the ContextPool as `"semantic-memory"`.
4. Run episodic decay (see Episodic Memory Decay section).

The LLM sees semantic memory in every system prompt, same as project context.

### 2. After-Turn Hook

Runs after each agent turn completes (in `hooks.py`).

**Responsibilities:**

1. Take the latest turn's content (user message + assistant response).
2. Make a lightweight LLM call with a focused extraction prompt.
3. The prompt asks: "Extract any user preferences, project facts, or conventions worth remembering. Return structured JSON or 'nothing'."
4. The prompt also receives current semantic memory contents so the LLM can merge/update existing topics.
5. If facts are returned: write/overwrite the relevant .md files in `semantic/`.
6. Update the `"semantic-memory"` item in the ContextPool so the current session reflects changes immediately.

**LLM extraction output format:**

```json
[
  {"topic": "user-preferences", "content": "Prefers spaces over tabs, 4-space indent."},
  {"topic": "testing-conventions", "content": "Uses pytest with fixture-based setup."}
]
```

**Write logic:**

- The `topic` field becomes the filename (`user-preferences.md`).
- If the file exists, the LLM receives existing content and produces a merged version. The body is replaced entirely.
- If new, create the file with frontmatter.
- Update the `updated` timestamp on every write.

### 3. Compaction Hook

Piggybacks on the existing compaction flow (in `compact.py`).

**Responsibilities:**

1. After compaction generates a summary, save a copy to `~/.coder/memory/episodic/` with an ISO timestamp filename.
2. No extra LLM call — reuses the summary already produced by compaction.
3. Purely a side effect: write the file, done.

## Episodic Memory Decay

Runs at startup (inside the startup hook). Age-based summarization:

| Age | Action |
|-----|--------|
| < 7 days | Keep as-is |
| 7–30 days | Merge into weekly summaries (`week-2026-W14.md`) |
| > 30 days | Merge into monthly summaries (`month-2026-03.md`) |

**Process:**

1. Read all episodic files.
2. Group by age bracket.
3. For each group needing merge, make one LLM call to summarize the batch.
4. Write the merged file, delete the individual source files.

Merged files use the same format with a `decay: weekly` or `decay: monthly` tag in frontmatter.

**Episodic memory is NOT loaded into the context pool by default.** It is available on demand via the `/recall` command or when the LLM asks about past sessions.

## System Prompt Integration

Two additions to the system prompt (in `prompt.py`):

### Semantic Memory Block

Injected from the context pool `"semantic-memory"` item:

```
## What You Know
<contents of all semantic memory files>
```

### Memory Awareness Instruction

Appended to the base prompt:

```
You have persistent memory stored in ~/.coder/memory/.
- Semantic memories (facts, preferences, conventions) are loaded above.
- Episodic memories (past session summaries) exist on disk. You cannot access them directly, but the user can search them with /recall.
- You do not need to manage memory explicitly — it is handled automatically.
- If the user says /remember or /forget, acknowledge the action.
```

## Explicit Commands

Three slash commands as overrides for autonomous behavior:

| Command | Behavior |
|---------|----------|
| `/remember <text>` | Forces a semantic memory write. LLM extracts topic and content from the user's text. |
| `/forget <topic>` | Deletes the corresponding .md file from `semantic/`. |
| `/memories` | Lists all semantic entries with their topics and last-updated dates. |
| `/recall <query>` | Grep-searches episodic memory file contents for the query string and displays matching entries. |

## What Does NOT Change

- **Working memory** — ContextPool and ContextQueue remain as-is.
- **Compaction logic** — unchanged, just gains a side effect (episodic write).
- **Tool system** — no new tools added. Memory is middleware, not tools.
- **Persona system** — unaffected.
