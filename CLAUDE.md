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
