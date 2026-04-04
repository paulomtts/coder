# coder/cli/repl.py
import asyncio
import sys
import threading

from pygents import ContextItem, Turn
from coder.cli.commands import is_slash_command, list_slash_commands, load_slash_command
from coder.agent.session import Session
from coder.shared.console import console


class _StdinReader:
    """Single-thread stdin reader that feeds an asyncio Queue.

    Ensures only one thread ever blocks on sys.stdin.readline, avoiding
    orphaned executor threads that steal input.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self) -> None:
        assert self._loop is not None
        while True:
            try:
                line = sys.stdin.readline()
                if not line:  # EOF
                    self._loop.call_soon_threadsafe(self._queue.put_nowait, None)
                    break
                self._loop.call_soon_threadsafe(
                    self._queue.put_nowait, line.rstrip("\n")
                )
            except (EOFError, KeyboardInterrupt):
                self._loop.call_soon_threadsafe(self._queue.put_nowait, None)
                break

    async def readline(self) -> str | None:
        return await self._queue.get()


_stdin = _StdinReader()


BUILTIN_COMMANDS = {"/help", "/role", "/quit", "/exit", "/quiet", "/verbose", "/debug"}


async def handle_input(session: Session, user_input: str) -> str | None:
    stripped = user_input.strip()
    cmd_word = stripped.split(None, 1)[0] if stripped else ""

    if stripped == "/help":
        commands = list_slash_commands(cwd=session.config.cwd)
        console.system("Built-in commands:")
        console.system("  /help          - Show this help")
        console.system(
            "  /role <name>   - Switch persona (scout, planner, worker, reviewer)"
        )
        console.system("  /role          - Clear active persona")
        console.system(
            "  /quiet         - Hide tool traces (show summary after each turn)"
        )
        console.system("  /verbose       - Show tool traces (default)")
        console.system(
            "  /debug         - Show debug logs (LLM calls, routing, context)"
        )
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
    if stripped in ("/quiet", "/verbose", "/debug"):
        old = console.verbosity
        new = stripped[1:]  # "quiet", "verbose", or "debug"
        console.set_verbosity(new)
        labels = {
            "quiet": "Tool traces hidden.",
            "verbose": "Tool traces visible.",
            "debug": "Debug logs enabled.",
        }
        console.system(f"Verbosity: {old} -> {new}. {labels[new]}")
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


async def run_agent(session: Session) -> None:
    """Consume agent.run() and render streamed text via console.response()."""
    collected_text = ""
    async for turn, value in session.agent.run():
        if isinstance(value, str):
            collected_text += value
    if collected_text:
        console.response(collected_text)


async def read_steering(session: Session, stop_event: asyncio.Event) -> None:
    """Background task: read from shared stdin reader and push into steering queue."""
    while not stop_event.is_set():
        try:
            line = await asyncio.wait_for(_stdin.readline(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        if line is None:
            break
        if line.strip():
            await session.steering_queue.put(line)


async def main(cwd: str | None = None) -> None:
    session = Session()
    await session.start(cwd=cwd)
    _stdin.start(asyncio.get_event_loop())
    console.system("coder ready. Type /help for commands, /quit to exit.\n")

    while True:
        try:
            sys.stdout.write(console.prompt())
            sys.stdout.flush()
            user_input = await _stdin.readline()
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
            await session.agent.put(Turn(session._llm_decide))

            # Run agent + background steering reader concurrently
            stop_event = asyncio.Event()
            steering_task = asyncio.create_task(read_steering(session, stop_event))
            try:
                await run_agent(session)
            finally:
                stop_event.set()
                steering_task.cancel()
                try:
                    await steering_task
                except asyncio.CancelledError:
                    pass

            console.flush_tool_summary()
            console.system("")
        except KeyboardInterrupt:
            console.system("\n\nInterrupted. Type /quit to exit.")
            continue
