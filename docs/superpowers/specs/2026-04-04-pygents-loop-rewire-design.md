# Pygents Loop Rewire — Design Spec

Restructure coder's agent loop to actually use pygents' `Agent.run()` and tool-driven flow control, replacing the manual `while` loop in `run_llm_call`. Implements the two-loop architecture from the [original spec](2026-04-01-coder-agent-design.md) using Approach B: split `llm_call` into `llm_decide` (structured) and `llm_respond` (streaming).

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM tool split | `llm_decide` + `llm_respond` | Avoids god-tool; separates decision-making from output streaming |
| Tool call granularity | One Turn per tool call | Maximizes hookability; each tool flows through agent queue individually |
| Flow control | Tool-driven only | Hooks are for side effects; only tools yield Turns |
| Streaming | Final response only | `llm_decide` uses structured output; `llm_respond` streams text |
| Toolkit injection | Fixed kwarg via lambda | `@tool(toolkit=lambda: session.toolkit)` — `llm_decide` and `llm_respond` are defined inside `create_agent()` which closes over `session` |
| Steering | Concurrent stdin reader | Background task reads stdin while agent runs |
| Compaction trigger | `before_invoke` hook on `llm_decide` | Fires before every LLM call, checks token pressure |
| Personas | Prompt overlay + tool filtering | No model switching (see backlog) |
| Re-entry | Self-enqueue | `llm_decide` yields tool Turns + `Turn(llm_decide)` at the end; FIFO guarantees order |

---

## 1. Core Loop

### Tool-driven turn flow

The REPL is the outer loop. When the user sends a message, it appends a user `ContextItem` to `cq` and enqueues `Turn(llm_decide)`. The pygents agent takes over via `agent.run()`:

```
User sends message
  -> REPL appends user ContextItem to cq, enqueues Turn(llm_decide)
    -> agent.run() starts processing queue
      -> llm_decide: structured LLM call
        -> yields ContextItem (assistant message -> cq via agent routing)
        -> Has tool calls?
          YES -> yields Turn(tool_read), Turn(tool_write), ..., Turn(llm_decide)
              -> each tool executes, yields ContextItem (result -> cq via agent routing)
              -> after all tools: llm_decide runs again (FIFO)
              -> loop continues
          NO  -> yields Turn(llm_respond)
              -> llm_respond: streaming LLM call, yields text chunks
              -> yields ContextItem (full assistant message -> cq via agent routing)
              -> queue empty, agent.run() exits
    -> REPL waits for next user input
```

### `llm_decide` — the decision tool

Async generator. Structured LLM call that decides: execute tools or respond to user.

```python
@tool(toolkit=lambda: session.toolkit)
async def llm_decide(cq: ContextQueue, pool: ContextPool, toolkit: PyAIToolkit):
    # 1. Assemble system prompt from pool (base-prompt, active-role, project-context, append-prompt)
    # 2. Build messages from cq.items, prepend compaction-summary from pool if present
    # 3. Build tool schemas from registered tools (excluding llm_decide, llm_respond)
    #    filtered by session.allowed_tools if a persona is active
    # 4. Structured LLM call -> AgentResponse(text, tool_calls)
    response = await toolkit.asend(response_model=AgentResponse, ...)

    # 5. Yield assistant message -> agent routes to cq
    yield ContextItem(content={"role": "assistant", ...})

    # 6. Route next step
    if response.tool_calls:
        for tc in response.tool_calls:
            yield Turn(tc.name, kwargs=tc.arguments)
        yield Turn(llm_decide)  # self-enqueue after all tools (FIFO)
    else:
        yield Turn(llm_respond)  # final text response
```

### `llm_respond` — the streaming tool

Async generator. Streaming LLM call that yields text chunks for the REPL to print.

```python
@tool(toolkit=lambda: session.toolkit)
async def llm_respond(cq: ContextQueue, pool: ContextPool, toolkit: PyAIToolkit):
    # 1. Assemble same prompt as llm_decide (pool + cq)
    # 2. Streaming LLM call (no tool schemas — text only)
    full_text = ""
    async for chunk in toolkit.stream(...):
        full_text += chunk
        yield chunk  # REPL prints this

    # 3. Yield full assistant message -> agent routes to cq
    yield ContextItem(content={"role": "assistant", "content": full_text})
```

### File/shell tools

Each tool yields a `ContextItem` with the result. No Turn yielding — they are leaf nodes.

```python
@tool()
async def tool_read(path: str, offset: int = None, limit: int = None):
    result = ...  # read file logic
    yield ContextItem(content={"role": "tool", "content": result})
```

### REPL consumption

The REPL iterates `agent.run()` and prints text chunks from `llm_respond`:

```python
async for turn, value in agent.run():
    if isinstance(value, str):  # text chunk from llm_respond
        sys.stdout.write(value)
        sys.stdout.flush()
```

`ContextItem` values are routed by the agent automatically and do not appear as `(turn, value)` pairs.

---

## 2. Steering

The REPL runs two concurrent tasks: the agent and a background stdin reader.

```python
async def main_loop():
    while True:
        user_input = await read_user_input()
        # ... handle slash commands ...
        await cq.append(ContextItem(content={"role": "user", "content": user_input}))
        await agent.put(Turn(llm_decide))

        async with asyncio.TaskGroup() as tg:
            tg.create_task(run_agent(agent))
            tg.create_task(read_steering(session))
```

A `before_turn` hook on the agent injects steering messages before `llm_decide` turns:

```python
@agent.before_turn
async def inject_steering(agent):
    if agent.current_turn.tool != llm_decide:
        return
    while not steering_queue.empty():
        msg = steering_queue.get_nowait()
        await agent.context_queue.append(
            ContextItem(content={"role": "user", "content": msg})
        )
```

The background reader exits when `agent.run()` completes (TaskGroup cancels it).

---

## 3. Compaction

A `before_invoke` hook on `llm_decide`. Fires every time the LLM is about to be called, checks token pressure.

```python
@llm_decide.before_invoke
async def check_compaction(cq: ContextQueue, pool: ContextPool, toolkit: PyAIToolkit):
    items = cq.items
    estimated_tokens = sum(len(str(item.content)) // 4 for item in items)
    max_tokens = 128_000
    if estimated_tokens < max_tokens * compaction_threshold:
        return

    # 1. Walk backward, keep recent items up to keep_recent_tokens
    # 2. Summarize old items via toolkit.chat()
    #    - No existing summary: SUMMARIZATION_PROMPT
    #    - Has existing summary in pool: UPDATE_SUMMARIZATION_PROMPT
    # 3. Store ContextItem(id="compaction-summary", description="Compacted conversation summary", content=summary) in pool
    # 4. Clear cq, re-append recent items
```

The compaction summary lives in the pool (has `id` + `description`). `llm_decide` reads it from the pool when assembling the prompt — it appears before conversation history.

Prompts are the same as the existing spec (copied from pi-mono): `SUMMARIZATION_PROMPT`, `UPDATE_SUMMARIZATION_PROMPT`, `TURN_PREFIX_SUMMARIZATION_PROMPT`, `BRANCH_SUMMARY_PROMPT`.

---

## 4. Personas

Single agent with prompt overlay and tool filtering. Four personas: scout, planner, worker, reviewer.

### What `switch_role(persona_name)` does

1. **Branch summary** — if there's conversation history, summarize via `toolkit.chat()` with `BRANCH_SUMMARY_PROMPT`. Store as `ContextItem(id="branch-summary", description="Summary of previous conversation branch", content=...)` in pool.

2. **Active role prompt** — store `ContextItem(id="active-role", description="Active role: {name}", content=persona.system_prompt)` in pool. `llm_decide` includes it when assembling the system prompt.

3. **Tool filtering** — set `session.allowed_tools`. `llm_decide` uses this to filter which tool schemas it sends to the LLM.

### What `clear_role()` does

Remove `active-role` from pool. Reset `allowed_tools` to None (all tools visible).

### Persona definitions

| Persona | Tool subset | Role |
|---------|-------------|------|
| Scout | read, bash, grep, find, ls | Fast recon, structured findings |
| Planner | read, bash (read-only), grep, find, ls | Analysis, numbered plans |
| Worker | all tools | Implements tasks |
| Reviewer | read, bash (read-only), grep, find, ls | Code review, structured feedback |

Persona system prompts are the same as the existing spec (copied from pi-mono).

### Chain workflows

Slash commands trigger sequential role switches. E.g., `/plan` runs scout then planner.

---

## 5. System Prompt Assembly

`llm_decide` and `llm_respond` both assemble the system prompt from pool items in fixed order:

1. `base-prompt` — default coding assistant prompt
2. `active-role` — persona system prompt (if active)
3. `project-context` — AGENTS.md / CLAUDE.md content
4. `append-prompt` — from `.coder/APPEND_SYSTEM.md`

Tool guidelines are generated dynamically based on which tools are registered and visible (filtered by `allowed_tools`).

The messages array is built from `cq.items`, with `compaction-summary` from pool prepended if present.

---

## 6. File Structure

```
coder/
    agent/
        loop.py              # create_agent(), register tools, attach hooks
                             # (steering: before_turn, compaction: before_invoke)
        session.py           # Session dataclass, start(), switch_role(), clear_role()
        llm/
            decide.py        # llm_decide tool
            respond.py       # llm_respond tool
            prompt.py        # System prompt assembly from pool items
        compaction/
            summarizer.py    # Compaction logic (existing, minor changes)
            prompts.py       # Compaction prompt templates (existing, no changes)
        personas/
            definitions.py   # Persona dataclass, PERSONAS dict (existing, no changes)
        tools/
            read.py, write.py, edit.py, bash.py, grep.py, find.py, ls.py
    cli/
        repl.py              # Outer loop, concurrent agent + stdin reader
        commands.py          # Slash command loading (existing, no changes)
    config/
        loader.py            # Config loading (existing, no changes)
        resources.py         # Project context discovery (existing, no changes)
    shared/
        constants.py         # Output limits (existing, no changes)
```

### Changes from current structure

| File | Change |
|------|--------|
| `agent/llm/call.py` | **Deleted** — replaced by `decide.py` + `respond.py` |
| `agent/llm/decide.py` | **New** — `llm_decide` tool |
| `agent/llm/respond.py` | **New** — `llm_respond` tool |
| `agent/loop.py` | **Rewritten** — loses `run_agent_loop()`, gains hook wiring + `create_agent()` with llm tools |
| `agent/session.py` | **Modified** — `start()` creates agent with llm tools, no more manual loop call |
| `cli/repl.py` | **Modified** — concurrent stdin reader + `agent.run()` consumption |
| Everything else | No changes |
