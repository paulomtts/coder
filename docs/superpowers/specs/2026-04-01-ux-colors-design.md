# UX Colors Design Spec

## Goal

Enhance the CLI UX by using colors and styling to visually distinguish different output types (agent internals vs. user-facing responses). Introduce a centralized "design system" via a `CoderConsole` wrapper so styling is consistent and easy to maintain.

## Dependencies

- **`rich`** — added to `pyproject.toml` as a runtime dependency.

## Theme System

Two theme variants for dark and light terminal backgrounds. Auto-detected at startup with a `force_theme` override option. Falls back to dark (most common).

### Color Palette

| Role                  | Dark Terminal        | Light Terminal         |
|-----------------------|----------------------|------------------------|
| LLM response text     | White                | Black                  |
| Response panel border | Green                | Dark green             |
| Tool name             | Yellow (dim)         | Dark yellow / olive    |
| Tool result preview   | Gray (dim)           | Dark gray (dim)        |
| Tool panel border     | Yellow (dim)         | Dark yellow (dim)      |
| System messages        | Cyan                 | Dark cyan              |
| Error label (`ERROR:`) | Bold red            | Bold red               |
| Error text            | Red                  | Red                    |
| Success messages      | Green                | Dark green             |
| User prompt (`> `)    | Bold green           | Bold green             |

### Theme Dataclass

```python
@dataclass
class Theme:
    response_text: str
    response_border: str
    tool_name: str
    tool_result: str
    tool_border: str
    system: str
    error_label: str
    error_text: str
    success: str
    prompt: str
```

## CoderConsole API

A wrapper class in `coder/shared/console.py` that owns a single `rich.Console` instance. The rest of the codebase imports the module-level singleton — never `rich` directly.

```python
class CoderConsole:
    def __init__(self, force_theme: str | None = None):
        """Auto-detects light/dark, or accepts 'light'/'dark' override."""

    def response(self, markdown_text: str) -> None:
        """Render LLM response as markdown inside a bordered panel."""

    def tool_trace(self, tool_name: str, result_preview: str) -> None:
        """Render a dimmed, collapsible tool call inside a panel.
        Format: [tool_name] result_preview (truncated)"""

    def system(self, message: str) -> None:
        """System messages: welcome, help, role switches."""

    def error(self, message: str) -> None:
        """ERROR: prefix in bold red, message in red."""

    def success(self, message: str) -> None:
        """Green-colored success confirmations."""

    def prompt(self) -> str:
        """Returns the styled prompt string for input."""
```

### Singleton

```python
console = CoderConsole()
```

Callers import via `from coder.shared.console import console`.

### Formatting Details

- **`response()`** — wraps `rich.markdown.Markdown` in a `rich.panel.Panel` with a green border.
- **`tool_trace()`** — uses a `Panel` with dim styling and `expand=False`. Multiple consecutive tool calls are visually grouped. Content is dimmed.
- **`error()`** — prints `ERROR:` as bold red label, followed by red message text. No panel, styled inline.
- **`success()`** — green text, no panel.
- **`system()`** — cyan text, no panel.
- **`prompt()`** — returns bold green `> ` string.

## Integration Points

### `coder/cli/repl.py`

| Current Code                              | Replacement                          |
|-------------------------------------------|--------------------------------------|
| Welcome message (line 74)                 | `console.system(...)`                |
| Help text (lines 29-37)                   | `console.system(...)`                |
| Role switch confirmations (lines 43, 51-52) | `console.system(...)`             |
| Error messages (lines 50-65)              | `console.error(...)`                 |
| Prompt `"> "` (line 77)                   | `console.prompt()`                   |
| Goodbye/interrupt messages                | `console.system(...)`                |

### `coder/agent/llm/call.py`

| Current Code                                  | Replacement                              |
|-----------------------------------------------|------------------------------------------|
| Tool call indicator + preview (lines 152-156) | `console.tool_trace(name, preview)`      |
| LLM text responses (lines 140, 183)          | `console.response(text)`                 |
| No-response fallback (line 188)               | `console.error("No response from LLM")` |

### Tool files

No changes. Tools return plain strings. Formatting happens at the call site in `call.py`.

## Files Changed

| File                          | Action   |
|-------------------------------|----------|
| `coder/shared/console.py`    | **New**  |
| `coder/cli/repl.py`          | Modify   |
| `coder/agent/llm/call.py`    | Modify   |
| `pyproject.toml`             | Modify   |
| `tests/test_console.py`      | **New**  |

## Testing

Unit tests in `tests/test_console.py`:

- Each method produces expected `rich` output (capture with `Console(file=StringIO())`).
- Theme switching — `force_theme="dark"` vs `force_theme="light"` apply different styles.
- `error()` output contains `ERROR:` prefix.
- `tool_trace()` output is dimmed and contains the tool name.
- `response()` renders markdown (e.g., `**bold**` becomes styled).

No integration/E2E tests — the integration is swapping `print()` calls. Manual REPL testing covers visual correctness.
