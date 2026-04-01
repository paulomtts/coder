import asyncio
import sys

from pygents import ContextItem
from coder.cli.commands import is_slash_command, list_slash_commands, load_slash_command
from coder.agent.session import Session
from coder.shared.console import console


async def read_user_input() -> str | None:
    loop = asyncio.get_event_loop()
    try:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            return None
        return line.rstrip("\n")
    except (EOFError, KeyboardInterrupt):
        return None


BUILTIN_COMMANDS = {"/help", "/role", "/quit", "/exit", "/quiet", "/verbose"}


async def handle_input(session: Session, user_input: str) -> str | None:
    stripped = user_input.strip()
    cmd_word = stripped.split(None, 1)[0] if stripped else ""

    if stripped == "/help":
        commands = list_slash_commands(cwd=session.config.cwd)
        console.system("Built-in commands:")
        console.system("  /help          - Show this help")
        console.system("  /role <name>   - Switch persona (scout, planner, worker, reviewer)")
        console.system("  /role          - Clear active persona")
        console.system("  /quiet         - Hide tool traces (show summary after each turn)")
        console.system("  /verbose       - Show tool traces (default)")
        console.system("  /quit          - Exit")
        if commands:
            console.system("\nSlash commands:")
            for cmd in commands:
                console.system(f"  /{cmd}")
        return None
    if cmd_word == "/role":
        parts = user_input.strip().split(None, 1)
        if len(parts) == 1:
            await session.clear_role()
            console.system("Cleared active role.")
        else:
            role_name = parts[1].strip()
            try:
                await session.switch_role(role_name)
                console.system(f"Switched to {role_name} role.")
            except KeyError:
                console.error(
                    f"Unknown role: {role_name}. Available: scout, planner, worker, reviewer"
                )
        return None
    if stripped in ("/quiet", "/verbose"):
        old = console.verbosity
        new = "quiet" if old == "normal" else "normal"
        console.set_verbosity(new)
        label = "Tool traces hidden." if new == "quiet" else "Tool traces visible."
        console.system(f"Verbosity: {old} -> {new}. {label}")
        return None
    if stripped in ("/quit", "/exit"):
        return None
    if is_slash_command(user_input):
        expanded = load_slash_command(user_input, cwd=session.config.cwd)
        if expanded is None:
            commands = list_slash_commands(cwd=session.config.cwd)
            if commands:
                console.error(
                    f"Unknown command. Available: {', '.join('/' + c for c in commands)}"
                )
            else:
                console.error(f"Unknown command: {cmd_word}")
            return None
        return expanded
    return user_input


async def main(cwd: str | None = None) -> None:
    session = Session()
    await session.start(cwd=cwd)
    console.system("coder ready. Type /help for commands, /quit to exit.\n")
    while True:
        try:
            sys.stdout.write(console.prompt())
            sys.stdout.flush()
            user_input = await read_user_input()
            if user_input is None or user_input.strip() in ("/quit", "/exit"):
                console.system("\nGoodbye.")
                break
            if not user_input.strip():
                continue
            message = await handle_input(session, user_input)
            if message is None:
                continue
            await session.cq.append(
                ContextItem(content={"role": "user", "content": message})
            )
            from coder.agent.loop import run_agent_loop

            await run_agent_loop(session)
            console.flush_tool_summary()
            console.system("")
        except KeyboardInterrupt:
            console.system("\n\nInterrupted. Type /quit to exit.")
            continue
