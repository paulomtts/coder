from types import SimpleNamespace

import pytest

from coder.server.runtime import run_session_turn


class FakeQueue:
    def __init__(self):
        self.items = []

    async def append(self, item):
        self.items.append(item)


class FakeAgent:
    def __init__(self):
        self.put_calls = []

    async def put(self, turn):
        self.put_calls.append(turn)


class FakeTokenStats:
    def __init__(self):
        self.reset_called = False

    def reset_turn(self):
        self.reset_called = True


@pytest.mark.asyncio
async def test_run_session_turn_emits_stream_events(monkeypatch):
    events = []

    async def emit(event):
        events.append(event)

    async def fake_stream(session):
        yield "Hel"
        yield "lo"

    session = SimpleNamespace(
        cq=FakeQueue(),
        agent=FakeAgent(),
        token_stats=FakeTokenStats(),
    )
    monkeypatch.setattr("coder.server.runtime._run_agent_stream", fake_stream)

    record = await run_session_turn(
        session_id="sess_123",
        user_text="hello",
        emit=emit,
        session=session,
    )

    assert [event.kind for event in events] == [
        "message.user_added",
        "assistant.delta",
        "assistant.delta",
        "assistant.completed",
    ]
    assert record.session_id == "sess_123"
    assert record.status.value == "idle"
    assert record.messages[0]["content"] == "hello"
    assert record.messages[-1]["content"] == "Hello"
    assert session.token_stats.reset_called is True
    assert len(session.agent.put_calls) == 1
    assert len(session.cq.items) == 1
