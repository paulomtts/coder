# Coder

A Python coding agent harness inspired by [pi-mono](https://github.com/badlogic/pi-mono/), built with [pygents](https://paulomtts.github.io/pygents/).

## Architecture

Feature-based package layout. The `agent/` package owns all agent internals;
`cli/` owns the local Python REPL; `server/` owns the FastAPI session service;
`config/` owns bootstrapping; `shared/` owns cross-cutting constants.

```
coder/
    agent/                       # Core agent orchestration
        loop.py                  # Agent creation, tool registration, hook wiring (steering, compaction)
        session.py               # Session lifecycle, context pool, role switching
        llm/                     # LLM integration boundary
            decide.py            # llm_decide tool — structured LLM call, yields Turns for tool execution
            respond.py           # llm_respond tool — streaming LLM call, yields text chunks
            prompt.py            # System prompt assembly, guidelines, tool schemas
        compaction/              # Context window management
            summarizer.py        # Token estimation, split logic, LLM-based summarization
            prompts.py           # All compaction/summarization prompt templates
        personas/                # Persona system
            definitions.py       # Persona dataclass, PERSONAS dict, prompt constants
        tools/                   # Tool implementations (pygents @tool decorators)
            read.py, write.py, edit.py, bash.py, grep.py, find.py, ls.py
    cli/                         # User interface
        repl.py                  # Interactive REPL loop, concurrent steering, agent.run() consumption
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

### Python CLI

```bash
uv run python main.py
```

### Python FastAPI service

```bash
uv run uvicorn coder.server.app:create_app --factory --reload
```

By default the service listens on `http://127.0.0.1:8000` and stores sessions on disk. For TUI-managed startup, the app also exposes `coder.server.main:app` as a stable uvicorn target.

### Bun TUI

```bash
cd tui
bun install
bun run dev
```

The TUI talks to the FastAPI service over HTTP + WebSocket streaming. If no server is already running at `CODER_API_URL` (or the default local address), the TUI will start one as a subprocess and shut it down when it exits.

The Bun runtime does not expose raw terminal input the same way Node does, so the TUI uses line-based commands in Bun mode:
- `/quit` to exit
- `/cancel` to cancel the active run
- `/up` / `/down` to scroll the transcript
- `/home` / `/end` to jump to the top/bottom

The view follows the latest message by default and switches to scrollback mode when you move away from the bottom.

## Testing

```bash
uv run pytest
cd tui && bun test
```

## Key conventions

- All tools are async pygents `@tool()` functions in `coder/agent/tools/`
- Tools import constants from `coder.shared.constants`
- The agent loop is tool-driven: llm_decide yields Turns, pygents Agent.run() processes the queue
- Compaction is triggered by a before_invoke hook on llm_decide
- Steering messages are injected via a before_turn hook on the agent
- System prompt is assembled from layered sources (base, role, project context, append)
- Config loads from `.env` -> env vars -> `.coder/config.yaml` (later overrides earlier)
