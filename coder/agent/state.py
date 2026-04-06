# coder/agent/state.py
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from coder.agent.session import Session

_session: Session | None = None


def set_session(session: Session) -> None:
    global _session
    _session = session


def get_session() -> Session:
    assert _session is not None, "Session not initialized"
    return _session
