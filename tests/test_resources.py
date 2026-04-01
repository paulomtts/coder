# tests/test_resources.py
import os
import pytest
from coder.config.resources import discover_project_context, load_system_prompt_override, load_append_prompt

def test_discover_agents_md(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Agent rules\nBe helpful.\n")
    result = discover_project_context(cwd=str(tmp_path))
    assert "Be helpful" in result

def test_discover_claude_md(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# Claude config\nUse TDD.\n")
    result = discover_project_context(cwd=str(tmp_path))
    assert "Use TDD" in result

def test_discover_walks_upward(tmp_path):
    (tmp_path / "AGENTS.md").write_text("root rules")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    result = discover_project_context(cwd=str(sub))
    assert "root rules" in result

def test_discover_no_files(tmp_path):
    result = discover_project_context(cwd=str(tmp_path))
    assert result == ""

def test_load_system_override(tmp_path):
    coder_dir = tmp_path / ".coder"
    coder_dir.mkdir()
    (coder_dir / "SYSTEM.md").write_text("Custom system prompt")
    result = load_system_prompt_override(cwd=str(tmp_path))
    assert result == "Custom system prompt"

def test_load_system_override_missing(tmp_path):
    result = load_system_prompt_override(cwd=str(tmp_path))
    assert result is None

def test_load_append_prompt(tmp_path):
    coder_dir = tmp_path / ".coder"
    coder_dir.mkdir()
    (coder_dir / "APPEND_SYSTEM.md").write_text("Extra instructions")
    result = load_append_prompt(cwd=str(tmp_path))
    assert result == "Extra instructions"

def test_load_append_prompt_missing(tmp_path):
    result = load_append_prompt(cwd=str(tmp_path))
    assert result is None
