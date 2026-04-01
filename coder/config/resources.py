# coder/config/resources.py
import os

CONTEXT_FILES = ["AGENTS.md", "CLAUDE.md"]

def discover_project_context(cwd: str) -> str:
    fragments: list[str] = []
    seen_paths: set[str] = set()
    current = os.path.abspath(cwd)
    while True:
        for name in CONTEXT_FILES:
            path = os.path.join(current, name)
            if os.path.isfile(path) and path not in seen_paths:
                seen_paths.add(path)
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().strip()
                if content:
                    fragments.append(f"# {path}\n{content}")
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    global_dir = os.path.expanduser("~/.coder/agent")
    if os.path.isdir(global_dir):
        for name in CONTEXT_FILES:
            path = os.path.join(global_dir, name)
            if os.path.isfile(path) and path not in seen_paths:
                seen_paths.add(path)
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().strip()
                if content:
                    fragments.append(f"# {path}\n{content}")
    return "\n\n".join(fragments)

def load_system_prompt_override(cwd: str) -> str | None:
    path = os.path.join(cwd, ".coder", "SYSTEM.md")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None

def load_append_prompt(cwd: str) -> str | None:
    path = os.path.join(cwd, ".coder", "APPEND_SYSTEM.md")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None
