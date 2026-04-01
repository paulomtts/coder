from dataclasses import dataclass

from rich.console import Console as RichConsole
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text


@dataclass(frozen=True)
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


DARK_THEME = Theme(
    response_text="white",
    response_border="green",
    tool_name="yellow",
    tool_result="bright_black",
    tool_border="yellow",
    system="cyan",
    error_label="bold red",
    error_text="red",
    success="green",
    prompt="bold green",
)

LIGHT_THEME = Theme(
    response_text="black",
    response_border="dark_green",
    tool_name="dark_goldenrod",
    tool_result="grey50",
    tool_border="dark_goldenrod",
    system="dark_cyan",
    error_label="bold red",
    error_text="red",
    success="dark_green",
    prompt="bold green",
)


def _detect_theme() -> Theme:
    """Detect terminal background and return appropriate theme.

    Falls back to dark theme (most common terminal setting).
    """
    return DARK_THEME


class CoderConsole:
    def __init__(self, force_theme: str | None = None) -> None:
        if force_theme == "light":
            self.theme = LIGHT_THEME
        elif force_theme == "dark":
            self.theme = DARK_THEME
        else:
            self.theme = _detect_theme()
        self._console = RichConsole()
        self.verbosity: str = "normal"
        self._tool_names: list[str] = []

    def set_verbosity(self, level: str) -> None:
        """Set verbosity level: 'quiet', 'normal', or 'verbose'."""
        self.verbosity = level

    def response(self, markdown_text: str) -> None:
        """Render LLM response as markdown inside a bordered panel."""
        md = Markdown(markdown_text)
        panel = Panel(
            md,
            border_style=self.theme.response_border,
            expand=True,
            padding=(0, 1),
        )
        self._console.print(panel)

    def tool_trace(self, tool_name: str, result_preview: str) -> None:
        """Render a dimmed tool call inside a compact panel."""
        if self.verbosity == "quiet":
            self._tool_names.append(tool_name)
            return
        label = Text(tool_name, style=self.theme.tool_name)
        content = Text(result_preview, style=self.theme.tool_result)
        combined = Text.assemble("[", label, "] ", content)
        panel = Panel(
            combined,
            border_style=self.theme.tool_border,
            expand=False,
            padding=(0, 1),
        )
        self._console.print(panel, style="dim")

    def flush_tool_summary(self) -> None:
        """Print a summary of buffered tool names and clear the buffer."""
        if not self._tool_names:
            return
        names = ", ".join(self._tool_names)
        count = len(self._tool_names)
        summary = Text(f"[{count} tools: {names}]", style=self.theme.tool_result)
        self._console.print(summary)
        self._tool_names = []

    def system(self, message: str) -> None:
        """System messages: welcome, help, role switches."""
        self._console.print(message, style=self.theme.system)

    def error(self, message: str) -> None:
        """ERROR: prefix in bold red, message in red."""
        text = Text.assemble(
            ("ERROR: ", self.theme.error_label),
            (message, self.theme.error_text),
        )
        self._console.print(text)

    def success(self, message: str) -> None:
        """Green-colored success confirmations."""
        self._console.print(message, style=self.theme.success, highlight=False)

    def prompt(self) -> str:
        """Returns the styled prompt string for input."""
        # Return ANSI-styled prompt string for use with sys.stdout.write
        text = Text("> ", style=self.theme.prompt)
        with self._console.capture() as capture:
            self._console.print(text, end="")
        return capture.get()


console = CoderConsole()
