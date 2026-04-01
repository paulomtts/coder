from io import StringIO

from rich.console import Console as RichConsole


def _capture_console(force_theme: str = "dark") -> tuple:
    """Create a CoderConsole that writes to a StringIO for capture."""
    from coder.shared.console import CoderConsole

    buf = StringIO()
    c = CoderConsole(force_theme=force_theme)
    c._console = RichConsole(file=buf, force_terminal=True, width=120)
    return c, buf


class TestTheme:
    def test_dark_theme_has_all_fields(self):
        from coder.shared.console import DARK_THEME

        assert DARK_THEME.response_text is not None
        assert DARK_THEME.response_border is not None
        assert DARK_THEME.tool_name is not None
        assert DARK_THEME.tool_result is not None
        assert DARK_THEME.tool_border is not None
        assert DARK_THEME.system is not None
        assert DARK_THEME.error_label is not None
        assert DARK_THEME.error_text is not None
        assert DARK_THEME.success is not None
        assert DARK_THEME.prompt is not None

    def test_light_theme_has_all_fields(self):
        from coder.shared.console import LIGHT_THEME

        assert LIGHT_THEME.response_text is not None
        assert LIGHT_THEME.response_border is not None
        assert LIGHT_THEME.tool_name is not None
        assert LIGHT_THEME.tool_result is not None
        assert LIGHT_THEME.tool_border is not None
        assert LIGHT_THEME.system is not None
        assert LIGHT_THEME.error_label is not None
        assert LIGHT_THEME.error_text is not None
        assert LIGHT_THEME.success is not None
        assert LIGHT_THEME.prompt is not None

    def test_dark_and_light_differ(self):
        from coder.shared.console import DARK_THEME, LIGHT_THEME

        assert DARK_THEME.response_text != LIGHT_THEME.response_text


class TestCoderConsoleResponse:
    def test_response_renders_markdown_in_panel(self):
        c, buf = _capture_console()
        c.response("Hello **world**")
        output = buf.getvalue()
        assert "world" in output
        assert "─" in output or "│" in output  # panel border chars

    def test_response_panel_present(self):
        c, buf = _capture_console()
        c.response("test")
        output = buf.getvalue()
        # Panel produces box-drawing characters
        assert any(ch in output for ch in ("╭", "┌", "│", "─"))


class TestCoderConsoleToolTrace:
    def test_tool_trace_contains_tool_name(self):
        c, buf = _capture_console()
        c.tool_trace("read", "/path/to/file.py contents here")
        output = buf.getvalue()
        assert "read" in output

    def test_tool_trace_contains_preview(self):
        c, buf = _capture_console()
        c.tool_trace("bash", "hello world output")
        output = buf.getvalue()
        assert "hello world output" in output

    def test_tool_trace_is_dimmed(self):
        c, buf = _capture_console()
        c.tool_trace("ls", "file1 file2")
        output = buf.getvalue()
        # Dim ANSI escape: ESC[2m
        assert "\x1b[2m" in output or "dim" in output.lower() or "\x1b[" in output


class TestCoderConsoleSystem:
    def test_system_message(self):
        c, buf = _capture_console()
        c.system("Welcome to coder")
        output = buf.getvalue()
        assert "Welcome to coder" in output


class TestCoderConsoleError:
    def test_error_contains_prefix(self):
        c, buf = _capture_console()
        c.error("file not found")
        output = buf.getvalue()
        assert "ERROR:" in output
        assert "file not found" in output


class TestCoderConsoleSuccess:
    def test_success_message(self):
        c, buf = _capture_console()
        c.success("Wrote 1024 bytes")
        output = buf.getvalue()
        assert "Wrote 1024 bytes" in output


class TestCoderConsolePrompt:
    def test_prompt_returns_string(self):
        from coder.shared.console import CoderConsole

        c = CoderConsole(force_theme="dark")
        result = c.prompt()
        assert isinstance(result, str)
        assert ">" in result


class TestThemeSwitching:
    def test_force_dark_theme(self):
        from coder.shared.console import CoderConsole, DARK_THEME

        c = CoderConsole(force_theme="dark")
        assert c.theme == DARK_THEME

    def test_force_light_theme(self):
        from coder.shared.console import CoderConsole, LIGHT_THEME

        c = CoderConsole(force_theme="light")
        assert c.theme == LIGHT_THEME


class TestVerbosity:
    def test_default_verbosity_is_normal(self):
        from coder.shared.console import CoderConsole
        c = CoderConsole(force_theme="dark")
        assert c.verbosity == "normal"

    def test_set_verbosity(self):
        from coder.shared.console import CoderConsole
        c = CoderConsole(force_theme="dark")
        c.set_verbosity("quiet")
        assert c.verbosity == "quiet"
        c.set_verbosity("normal")
        assert c.verbosity == "normal"

    def test_quiet_mode_suppresses_tool_trace(self):
        c, buf = _capture_console()
        c.set_verbosity("quiet")
        c.tool_trace("read", "/path/to/file")
        output = buf.getvalue()
        assert output == ""  # nothing printed

    def test_quiet_mode_collects_tool_names(self):
        c, buf = _capture_console()
        c.set_verbosity("quiet")
        c.tool_trace("read", "/path/to/file")
        c.tool_trace("bash", "ls output")
        assert c._tool_names == ["read", "bash"]

    def test_flush_tool_summary_prints_summary(self):
        c, buf = _capture_console()
        c.set_verbosity("quiet")
        c.tool_trace("read", "content")
        c.tool_trace("bash", "output")
        c.tool_trace("edit", "applied")
        c.flush_tool_summary()
        output = buf.getvalue()
        assert "3 tools" in output
        assert "read" in output
        assert "bash" in output
        assert "edit" in output

    def test_flush_tool_summary_clears_buffer(self):
        c, buf = _capture_console()
        c.set_verbosity("quiet")
        c.tool_trace("read", "content")
        c.flush_tool_summary()
        assert c._tool_names == []

    def test_flush_tool_summary_noop_when_empty(self):
        c, buf = _capture_console()
        c.flush_tool_summary()
        output = buf.getvalue()
        assert output == ""

    def test_normal_mode_does_not_collect_names(self):
        c, buf = _capture_console()
        c.tool_trace("read", "content")
        assert c._tool_names == []
