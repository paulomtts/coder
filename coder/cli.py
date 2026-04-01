import asyncio
import sys

from pygents import ContextItem, Turn
from coder.prompts import is_slash_command, list_slash_commands, load_slash_command
from coder.session import Session


async def read_user_input() -> str | None:
    loop = asyncio.get_event_loop()
    try:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            return None
        return line.rstrip("\n")
    except (EOFError, KeyboardInterrupt):
        return None


async def handle_input(session: Session, user_input: str) -> str | None:
    if is_slash_command(user_input):
        expanded = load_slash_command(user_input, cwd=session.config.cwd)
        if expanded is None:
            commands = list_slash_commands(cwd=session.config.cwd)
            if commands:
                print(f"Unknown command. Available: {', '.join('/' + c for c in commands)}")
            else:
                print("No slash commands found in .coder/prompts/")
            return None
        return expanded
    if user_input.strip() == "/help":
        commands = list_slash_commands(cwd=session.config.cwd)
        print("Built-in commands:")
        print("  /help          - Show this help")
        print("  /role <name>   - Switch persona (scout, planner, worker, reviewer)")
        print("  /role          - Clear active persona")
        print("  /quit          - Exit")
        if commands:
            print("\nSlash commands:")
            for cmd in commands:
                print(f"  /{cmd}")
        return None
    if user_input.strip().startswith("/role"):
        parts = user_input.strip().split(None, 1)
        if len(parts) == 1:
            await session.clear_role()
            print("Cleared active role.")
        else:
            role_name = parts[1].strip()
            try:
                await session.switch_role(role_name)
                print(f"Switched to {role_name} role.")
            except KeyError:
                print(f"Unknown role: {role_name}. Available: scout, planner, worker, reviewer")
        return None
    if user_input.strip() in ("/quit", "/exit"):
        return None
    return user_input


async def main(cwd: str | None = None) -> None:
    session = Session()
    await session.start(cwd=cwd)
    print("coder ready. Type /help for commands, /quit to exit.\n")
    while True:
        try:
            sys.stdout.write("> ")
            sys.stdout.flush()
            user_input = await read_user_input()
            if user_input is None or user_input.strip() in ("/quit", "/exit"):
                print("\nGoodbye.")
                break
            if not user_input.strip():
                continue
            message = await handle_input(session, user_input)
            if message is None:
                continue
            await session.cq.append(ContextItem(content={"role": "user", "content": message}))
            from coder.agent_loop import run_agent_loop
            await run_agent_loop(session)
            print()
        except KeyboardInterrupt:
            print("\n\nInterrupted. Type /quit to exit.")
            continue
