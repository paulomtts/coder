from __future__ import annotations

from typing import Any

from coder.server.protocol import StreamEvent


def make_event(session_id: str, kind: str, **data: Any) -> StreamEvent:
    return StreamEvent(kind=kind, session_id=session_id, data=data)


async def emit_event(emit, event: StreamEvent) -> None:
    result = emit(event)
    if hasattr(result, "__await__"):
        await result
