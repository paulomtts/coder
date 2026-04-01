import os
import pytest
from coder.cli.commands import load_slash_command, list_slash_commands, is_slash_command

def test_is_slash_command():
    assert is_slash_command("/plan fix the bug")
    assert is_slash_command("/pr")
    assert not is_slash_command("hello")
    assert not is_slash_command("")

def test_load_slash_command(tmp_path):
    prompts_dir = tmp_path / ".coder" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "plan.md").write_text("Create a plan for: $ARGUMENTS")
    result = load_slash_command("/plan fix the auth bug", cwd=str(tmp_path))
    assert result == "Create a plan for: fix the auth bug"

def test_load_slash_command_dollar_at(tmp_path):
    prompts_dir = tmp_path / ".coder" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "pr.md").write_text("Review PR $@")
    result = load_slash_command("/pr 123", cwd=str(tmp_path))
    assert result == "Review PR 123"

def test_load_slash_command_no_args(tmp_path):
    prompts_dir = tmp_path / ".coder" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "cl.md").write_text("Run changelog audit")
    result = load_slash_command("/cl", cwd=str(tmp_path))
    assert result == "Run changelog audit"

def test_load_slash_command_not_found(tmp_path):
    result = load_slash_command("/missing", cwd=str(tmp_path))
    assert result is None

def test_list_slash_commands(tmp_path):
    prompts_dir = tmp_path / ".coder" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "plan.md").write_text("")
    (prompts_dir / "pr.md").write_text("")
    (prompts_dir / "not_md.txt").write_text("")
    commands = list_slash_commands(cwd=str(tmp_path))
    assert "plan" in commands
    assert "pr" in commands
    assert "not_md" not in commands
