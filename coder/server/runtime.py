from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from pygents import ContextItem, Turn
from pygents.registry import ToolRegistry

from coder.agent.session import Session
from coder.agent.state import set_session
from coder.agent.tools.llm_decide import llm_decide
from coder.server.hooks import emit_event, make_event
from coder.server.protocol import SessionRecord, SessionStatus, StreamEvent

StreamEmitter = Callable[[StreamEvent], Awaitable[None] | None]


async def _run_agent_stream(session: Any) -> AsyncGenerator[str, None]:
    async for _turn, value in session.agent.run():
        if isinstance(value, str):
            yield value


async def run_session_turn(
    session_id: str,
    user_text: str,
    emit: StreamEmitter,
    *,
    cwd: str | None = None,
    session: Any | None = None,
) -> SessionRecord:
    if session is None:
        session = Session()
        try:
            await session.start(cwd=cwd)
        except Exception as exc:
            await emit_event(
                emit,
                make_event(session_id, "session.error", error=str(exc)),
            )
            raise

    set_session(session)

    now = datetime.now(timezone.utc)
    record = SessionRecord(
        session_id=session_id,
        status=SessionStatus.running,
        messages=[{"role": "user", "content": user_text}],
        created_at=now,
        updated_at=now,
        cwd=cwd,
    )

    await emit_event(
        emit,
        make_event(session_id, "message.user_added", role="user", content=user_text),
    )

    if hasattr(session, "cq"):
        await session.cq.append(ContextItem(content={"role": "user", "content": user_text}))

    if hasattr(session, "token_stats"):
        session.token_stats.reset_turn()

    if hasattr(session, "agent"):
        try:
            ToolRegistry.get(llm_decide.__name__)
        except Exception:
            ToolRegistry.register(llm_decide)
        await session.agent.put(Turn(llm_decide))

    collected: list[str] = []
    try:
        async for chunk in _run_agent_stream(session):
            collected.append(chunk)
            await emit_event(
                emit,
                make_event(session_id, "assistant.delta", text=chunk),
            )
        assistant_text = "".join(collected)
        if assistant_text:
            record.messages.append({"role": "assistant", "content": assistant_text})
        await emit_event(
            emit,
            make_event(session_id, "assistant.completed", text=assistant_text),
        )
        record.status = SessionStatus.idle
    except Exception as exc:
        record.status = SessionStatus.error
        await emit_event(
            emit,
            make_event(session_id, "session.error", error=str(exc)),
        )
        raise
    finally:
        record.updated_at = datetime.now(timezone.utc)

    return record
