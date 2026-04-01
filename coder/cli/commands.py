import os


def is_slash_command(text: str) -> bool:
    return bool(text) and text.startswith("/") and len(text) > 1


def load_slash_command(text: str, cwd: str) -> str | None:
    parts = text.split(None, 1)
    command = parts[0][1:]
    arguments = parts[1] if len(parts) > 1 else ""
    prompts_dir = os.path.join(cwd, ".coder", "prompts")
    template_path = os.path.join(prompts_dir, f"{command}.md")
    if not os.path.isfile(template_path):
        return None
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
    result = template.replace("$ARGUMENTS", arguments)
    result = result.replace("$@", arguments)
    return result


def list_slash_commands(cwd: str) -> list[str]:
    prompts_dir = os.path.join(cwd, ".coder", "prompts")
    if not os.path.isdir(prompts_dir):
        return []
    commands = []
    for name in sorted(os.listdir(prompts_dir)):
        if name.endswith(".md"):
            commands.append(name[:-3])
    return commands
