# Coder

A Python coding agent harness inspired by [pi-mono](https://github.com/badlogic/pi-mono/).

## Architecture

Feature-based package layout. The `agent/` package owns all agent internals;
`cli/` owns user interaction; `config/` owns bootstrapping; `shared/` owns
cross-cutting constants.

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
- The agent loop is tool-driven: llm_decide yields Turns, pygents Agent.run() processes the queue
- Compaction is triggered by a before_invoke hook on llm_decide
- Steering messages are injected via a before_turn hook on the agent
- System prompt is assembled from layered sources (base, role, project context, append)
- Config loads from `.env` -> env vars -> `.coder/config.yaml` (later overrides earlier)
