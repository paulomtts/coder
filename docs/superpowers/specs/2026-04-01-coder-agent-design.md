# Coder Agent — Design Spec

A Python replication of [badlogic/pi-mono](https://github.com/badlogic/pi-mono)'s coding agent, built on **pygents** (agent orchestration) and **py-ai-toolkit** (LLM communication).

## Decisions

| Decision | Choice |
|----------|--------|
| Scope | Full replication (all 6 pi-mono subsystems) |
| LLM layer | py-ai-toolkit (OpenAI-compatible, Jinja2 templates, streaming) |
| Agent framework | pygents (tools, turns, hooks, context injection) |
| Tool execution | Direct (no sandbox) |
| UI | CLI only (stdin/stdout streaming) |
| Compaction | LLM-based via `toolkit.chat()` |
| Subagents | Single agent, role-switching via prompt/tool-set swaps |

---

## 1. Architecture

Five layers:

```
CLI (stdin/stdout)
  → Session Manager (config, prompt assembly, role switching, slash commands)
    → pygents Agent (single, tool-driven two-loop orchestration)
      → Tool Layer (read, write, edit, bash, grep, find, ls, llm_call)
        → py-ai-toolkit (chat/stream for LLM communication)
```

The LLM call is itself a pygents tool (`llm_call`). It assembles the prompt from ContextQueue (history) + ContextPool (system state), calls `toolkit.stream()`, parses tool calls from the response, and returns `Turn` objects to chain the next step. The agent auto-enqueues returned Turns.

The outer loop (follow-up messages) is the CLI's main loop — when `agent.run()` finishes (queue empty), it waits for user input and enqueues a new `Turn(llm_call)`.

---

## 2. Context Management

### ContextQueue — conversation history

Bounded sliding window (configurable limit, default 50). Each item wraps a message dict:

```python
ContextItem(content={"role": "user", "content": "Fix the bug in auth.py"})
ContextItem(content={"role": "assistant", "content": "I'll read the file first."})
ContextItem(content={"role": "assistant", "tool_calls": [...]})
ContextItem(content={"role": "tool", "tool_call_id": "...", "content": "file contents..."})
```

The `llm_call` tool reads `cq.items` to build the messages array. Compaction is triggered by a `before_invoke` hook on `llm_call` that checks token pressure before each LLM call (see Section 5).

### ContextPool — system state

Keyed store for named prompt fragments:

| ID | Description | Content |
|----|-------------|---------|
| `base-prompt` | Default system prompt | Base coding assistant prompt (from pi-mono) |
| `project-context` | AGENTS.md / CLAUDE.md content | Loaded from disk at session start |
| `skills-index` | Available skills listing | XML block of skill names + descriptions |
| `append-prompt` | User's append block | From `.coder/APPEND_SYSTEM.md` |
| `compaction-summary` | Latest compaction checkpoint | Structured summary when compaction fires |
| `active-role` | Current subagent persona | System prompt overlay for Scout/Planner/etc. |

The `llm_call` tool assembles the system prompt by concatenating pool items in fixed order: `base-prompt` → `active-role` → `project-context` → `skills-index` → `append-prompt`.

Context injection: tools declare `cq: ContextQueue` or `pool: ContextPool` in their signature and get the agent's instances automatically.

---

## 3. Tool Layer

Seven file/shell tools plus the `llm_call` orchestration tool. All are `@tool()` decorated async functions.

### File/shell tools

#### read

- **Description**: Read the contents of a file. Supports text files and images (jpg, png, gif, webp). Images are sent as attachments. For text files, output is truncated to 2000 lines or 256KB (whichever is hit first). Use offset/limit for large files. When you need the full file, continue with offset until complete.
- **Parameters**: `path` (str, required), `offset` (int, optional, 1-indexed), `limit` (int, optional)
- **Guideline**: Use read to examine files instead of cat or sed.

#### write

- **Description**: Write content to a file. Creates the file if it doesn't exist, overwrites if it does. Automatically creates parent directories.
- **Parameters**: `path` (str, required), `content` (str, required)
- **Guideline**: Use write only for new files or complete rewrites.

#### edit

- **Description**: Edit a single file using exact text replacement. Every edits[].oldText must match a unique, non-overlapping region of the original file. If two changes affect the same block or nearby lines, merge them into one edit instead of emitting overlapping edits. Do not include large unchanged regions just to connect distant changes.
- **Parameters**: `path` (str, required), `edits` (list of `{old_text: str, new_text: str}`, required)
- **Guidelines**:
  - Use edit for precise changes (edits[].oldText must match exactly)
  - When changing multiple separate locations in one file, use one edit call with multiple entries in edits[] instead of multiple edit calls
  - Each edits[].oldText is matched against the original file, not after earlier edits are applied. Do not emit overlapping or nested edits. Merge nearby changes into one edit.
  - Keep edits[].oldText as small as possible while still being unique in the file. Do not pad with large unchanged regions.

#### bash

- **Description**: Execute a bash command in the current working directory. Returns stdout and stderr. Output is truncated to last 2000 lines or 256KB (whichever is hit first). If truncated, full output is saved to a temp file. Optionally provide a timeout in seconds.
- **Parameters**: `command` (str, required), `timeout` (int, optional, no default timeout)

#### grep

- **Description**: Search file contents for a pattern. Returns matching lines with file paths and line numbers. Respects .gitignore. Output is truncated to 100 matches or 256KB (whichever is hit first).
- **Parameters**: `pattern` (str, required), `path` (str, optional), `glob` (str, optional), `ignore_case` (bool, optional), `literal` (bool, optional), `context` (int, optional), `limit` (int, optional, default 100)

#### find

- **Description**: Search for files by glob pattern. Returns matching file paths relative to the search directory. Respects .gitignore. Output is truncated to 1000 results or 256KB (whichever is hit first).
- **Parameters**: `pattern` (str, required), `path` (str, optional), `limit` (int, optional, default 1000)

#### ls

- **Description**: List directory contents. Returns entries sorted alphabetically, with '/' suffix for directories. Includes dotfiles. Output is truncated to 500 entries or 256KB (whichever is hit first).
- **Parameters**: `path` (str, optional, default cwd), `limit` (int, optional, default 500)

### llm_call — the orchestration tool

```python
@tool()
async def llm_call(cq: ContextQueue, pool: ContextPool) -> str | Turn:
    # 1. Assemble system prompt from pool items in fixed order
    # 2. Build messages array from cq.items
    # 3. Build tool schemas from registered tools (excluding llm_call itself)
    # 4. Call toolkit.stream() with system + messages + tools
    # 5. Stream text to stdout as it arrives
    # 6. If response contains tool calls:
    #      - Append assistant message (with tool_calls) to cq
    #      - Return Turn for first tool call; enqueue rest via agent.put()
    # 7. If no tool calls:
    #      - Append assistant message to cq
    #      - Return the text response
```

Tool schemas sent to the LLM exclude `llm_call` — only the seven file/shell tools are exposed.

### Tool guideline injection

Each tool contributes a `prompt_guideline` string. These are assembled dynamically based on which tools are registered and injected into the system prompt's guidelines section. When bash is present alongside grep/find/ls, the guideline becomes: "Prefer grep/find/ls tools over bash for file exploration (faster, respects .gitignore)."

---

## 4. Two-Loop Design

### Inner loop (tool calls + steering)

```
User sends message
  → CLI enqueues Turn(llm_call)
    → llm_call streams response
      → Response has tool calls?
        YES → appends assistant msg to cq
            → returns Turn(tool_x) for first tool call
            → enqueues Turn(tool_y), Turn(tool_z) for remaining
            → each tool executes, appends result to cq
            → after_turn hook enqueues Turn(llm_call) to send results back
            → loop continues
        NO  → appends assistant msg to cq
            → returns final text
            → queue empties, agent.run() exits
```

Re-entry mechanism: an `after_turn` hook on the agent — after a file/shell tool completes, if there are no more tool turns queued but the last assistant message had tool calls, it enqueues `Turn(llm_call)`.

### Steering messages

Mid-run user input. The CLI runs a background task reading stdin. When user types while the agent is working, the message is stored in a steering queue. The `before_turn` hook checks this queue before each `llm_call` turn and prepends any steering messages to `cq`.

### Outer loop (follow-ups)

```python
async def main_loop():
    while True:
        user_input = await read_user_input()
        if user_input is None:
            break
        await cq.append(ContextItem(content={"role": "user", "content": user_input}))
        await agent.put(Turn(llm_call))
        async for turn, value in agent.run():
            pass  # text already streamed by llm_call
```

### Stop conditions

1. **Natural completion** — no tool calls, no steering messages, queue empties
2. **LLM error** — `llm_call` catches API errors, appends error to cq, does not re-enqueue
3. **Abort** — Ctrl+C caught by CLI

---

## 5. Compaction

### Trigger

A `before_invoke` hook on `llm_call` estimates token count (`len(content) // 4` for each message). When it exceeds `compaction_threshold` (default 80%) of the model's context window, compaction fires.

### Flow

1. Walk backward through `cq.items`, keeping recent items until `keep_recent_tokens` (default 20,000) are preserved
2. Split into `old_messages` (to summarize) and `recent_messages` (to keep)
3. If no existing summary: call `toolkit.chat()` with `SUMMARIZATION_PROMPT` + old messages
4. If existing summary: call `toolkit.chat()` with `UPDATE_SUMMARIZATION_PROMPT` + existing summary + old messages
5. Store summary as `ContextItem(id="compaction-summary", ...)` in pool
6. Clear cq, re-append recent messages

### Summarization prompts

All copied verbatim from pi-mono.

#### SUMMARIZATION_SYSTEM_PROMPT

```
You are a context summarization assistant. Your task is to read a conversation between a user and an AI coding assistant, then produce a structured summary following the exact format specified.

Do NOT continue the conversation. Do NOT respond to any questions in the conversation. ONLY output the structured summary.
```

#### SUMMARIZATION_PROMPT

```
The messages above are a conversation to summarize. Create a structured context checkpoint summary that another LLM will use to continue the work.

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

Keep each section concise. Preserve exact file paths, function names, and error messages.
```

#### UPDATE_SUMMARIZATION_PROMPT

```
The messages above are NEW conversation messages to incorporate into the existing summary provided in <previous-summary> tags.

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

Keep each section concise. Preserve exact file paths, function names, and error messages.
```

#### TURN_PREFIX_SUMMARIZATION_PROMPT

```
This is the PREFIX of a turn that was too large to keep. The SUFFIX (recent work) is retained.

Summarize the prefix to provide context for the retained suffix:

## Original Request
[What did the user ask for in this turn?]

## Early Progress
- [Key decisions and work done in the prefix]

## Context for Suffix
- [Information needed to understand the retained recent work]

Be concise. Focus on what's needed to understand the kept suffix.
```

#### BRANCH_SUMMARY_PROMPT

```
Create a structured summary of this conversation branch for context when returning later.

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

Keep each section concise. Preserve exact file paths, function names, and error messages.
```

#### BRANCH_SUMMARY_PREAMBLE

```
The user explored a different conversation branch before returning here.
Summary of that exploration:
```

---

## 6. Subagent Personas (Role Switching)

Single agent with prompt/tool-set swaps. Four personas:

| Persona | Model hint | Tool subset | Role |
|---------|-----------|-------------|------|
| Scout | fast/cheap (e.g. haiku) | read, bash, grep, find, ls | Fast recon, outputs structured findings |
| Planner | mid-tier (e.g. sonnet) | read, bash (read-only), grep, find, ls | Analysis, produces numbered plans |
| Worker | mid-tier (e.g. sonnet) | all 7 tools | Implements tasks, outputs completion report |
| Reviewer | mid-tier (e.g. sonnet) | read, bash (read-only), grep, find, ls | Code review, outputs structured feedback |

### Role switching

`switch_role(persona_name)` updates three things:

1. **System prompt overlay** — stores `ContextItem(id="active-role", ...)` in pool with persona's system prompt
2. **Model config** — swaps `PyAIToolkit.main_model_config` to the persona's preferred model
3. **Tool filter** — sets `allowed_tools: set[str]` that `llm_call` uses to filter which tool schemas the LLM sees

Before switching, if there's conversation history, `BRANCH_SUMMARY_PROMPT` runs to produce a handoff summary.

### Persona prompts

Copied verbatim from pi-mono.

#### Scout

```
You are a scout. Quickly investigate a codebase and return structured findings that another agent can use without re-reading everything.

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
1. `path/to/file.ts` (lines 10-50) - Description of what's here
2. `path/to/other.ts` (lines 100-150) - Description
3. ...

## Key Code
Critical types, interfaces, or functions (actual code from the files).

## Architecture
Brief explanation of how the pieces connect.

## Start Here
Which file to look at first and why.
```

#### Planner

```
You are a planning specialist. You receive context (from a scout) and requirements, then produce a clear implementation plan.

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

Keep the plan concrete. The worker agent will execute it verbatim.
```

#### Worker

```
You are a worker agent with full capabilities. You operate in an isolated context window to handle delegated tasks without polluting the main conversation.

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
- Key functions/types touched (short list)
```

#### Reviewer

```
You are a senior code reviewer. Analyze code for quality, security, and maintainability.

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

Be specific with file paths and line numbers.
```

### Chain workflows

Sequences of role switches with prompts:

- `scout > plan`: `switch_role("scout")` → run → `switch_role("planner")` → run
- `full pipeline`: scout → planner → worker → reviewer

Exposed via slash commands (e.g. `/plan` runs scout then planner).

---

## 7. Prompt Templates (Slash Commands) & Session Manager

### Slash commands

Prompt templates loaded from `.coder/prompts/`:

| Command | File | Purpose |
|---------|------|---------|
| `/cl` | `cl.md` | Changelog audit before release |
| `/is` | `is.md` | GitHub issue analysis |
| `/pr` | `pr.md` | PR review with structured output |
| `/wr` | `wr.md` | Wrap task (changelog, commit, push) |
| `/plan` | `plan.md` | Run scout → planner chain |

Templates support `$ARGUMENTS` / `$@` substitution. When the CLI sees a `/` prefix, it loads the matching template, substitutes arguments, and injects it as a user message.

Custom commands are `.md` files dropped into `.coder/prompts/` — no registration needed.

### Session Manager

```python
class Session:
    agent: Agent           # the single pygents agent
    toolkit: PyAIToolkit   # LLM client
    pool: ContextPool      # system state
    cq: ContextQueue       # conversation history
    config: SessionConfig  # model, thresholds, cwd, etc.
```

### Startup sequence

1. Load config (env vars, `.coder/config.yaml` if present)
2. Initialize `PyAIToolkit` with model config
3. Register all tools via `@tool()`
4. Create `ContextPool` and populate: `base-prompt`, `project-context` (walk AGENTS.md/CLAUDE.md from cwd to root), `skills-index`, `append-prompt`
5. Create `ContextQueue(limit=config.history_limit)`
6. Create `Agent("coder", "Coding assistant", tools, context_pool=pool, context_queue=cq)`
7. Attach hooks (compaction, steering, re-entry)
8. Enter main loop

### Project context discovery

Walk from cwd upward, collecting `AGENTS.md` and `CLAUDE.md` files, plus `~/.coder/agent/` for global config.

### Default base system prompt

Adapted from pi-mono (replacing "pi" with "coder"):

```
You are an expert coding assistant operating inside coder, a coding agent harness.
You help users by reading files, executing commands, editing code, and writing new files.

Available tools:
{tools_list}

In addition to the tools above, you may have access to other custom tools depending on the project.

Guidelines:
{guidelines}
```

Guidelines are dynamic based on registered tools:
- When bash is present but no grep/find/ls: "Use bash for file operations like ls, rg, find"
- When bash AND grep/find/ls are present: "Prefer grep/find/ls tools over bash for file exploration (faster, respects .gitignore)"
- Always: "Be concise in your responses"
- Always: "Show file paths clearly when working with files"

### Prompt override mechanism

| File | Effect |
|------|--------|
| `.coder/SYSTEM.md` | Replaces the entire default base prompt |
| `.coder/APPEND_SYSTEM.md` | Appends to whatever base prompt is active |

### Config

| Setting | Default | Source |
|---------|---------|--------|
| `model` | from env `LLM_MODEL` | env / config file |
| `api_key` | from env `LLM_API_KEY` | env / config file |
| `history_limit` | 50 | config file |
| `compaction_threshold` | 0.8 | config file |
| `keep_recent_tokens` | 20000 | config file |

---

## File Structure

```
coder/
├── main.py                      # CLI entry point, main loop
├── session.py                   # Session manager, config, startup
├── agent_loop.py                # Agent setup, hooks, two-loop wiring
├── llm_call.py                  # The llm_call tool
├── tools/
│   ├── __init__.py
│   ├── read.py
│   ├── write.py
│   ├── edit.py
│   ├── bash.py
│   ├── grep.py
│   ├── find.py
│   └── ls.py
├── compaction.py                # Compaction logic and prompts
├── personas.py                  # Role switching and persona prompts
├── prompts.py                   # Slash command loading and substitution
├── resources.py                 # Project context discovery (AGENTS.md, etc.)
└── .coder/
    ├── prompts/                 # Slash command templates
    │   ├── cl.md
    │   ├── is.md
    │   ├── pr.md
    │   ├── wr.md
    │   └── plan.md
    ├── config.yaml              # Optional config
    ├── SYSTEM.md                # Optional system prompt override
    └── APPEND_SYSTEM.md         # Optional system prompt append
```
