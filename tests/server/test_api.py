from datetime import datetime, timezone

from fastapi.testclient import TestClient

from coder.server.app import create_app
from coder.server.protocol import SessionRecord, SessionStatus, StreamEvent


def test_create_session_and_stream(monkeypatch, tmp_path):
    client = TestClient(create_app(base_dir=tmp_path))

    async def fake_run_session_turn(session_id, user_text, emit, cwd=None, session=None):
        await emit(
            StreamEvent(
                kind="message.user_added",
                session_id=session_id,
                data={"role": "user", "content": user_text},
            )
        )
        await emit(
            StreamEvent(
                kind="assistant.completed",
                session_id=session_id,
                data={"text": "hello back"},
            )
        )
        return SessionRecord(
            session_id=session_id,
            status=SessionStatus.idle,
            messages=[{"role": "user", "content": user_text}],
        )

    monkeypatch.setattr("coder.server.app.run_session_turn", fake_run_session_turn)

    response = client.post("/sessions")
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    with client.websocket_connect(f"/sessions/{session_id}/stream") as ws:
        post = client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "hello"},
        )
        assert post.status_code == 200
        event = ws.receive_json()
        assert event["kind"] in {"message.user_added", "assistant.completed"}


def test_post_message_preserves_existing_transcript(monkeypatch, tmp_path):
    client = TestClient(create_app(base_dir=tmp_path))
    app = client.app
    hub = app.state.hub
    session_id = "sess_123"
    hub.store.save(
        SessionRecord(
            session_id=session_id,
            status=SessionStatus.idle,
            messages=[
                {"role": "user", "content": "previous question"},
                {"role": "assistant", "content": "previous answer"},
            ],
            created_at=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 15, 10, 1, tzinfo=timezone.utc),
        )
    )

    async def fake_run_session_turn(session_id, user_text, emit, cwd=None, session=None):
        return SessionRecord(
            session_id=session_id,
            status=SessionStatus.idle,
            messages=[
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": "new answer"},
            ],
            created_at=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 15, 10, 2, tzinfo=timezone.utc),
        )

    monkeypatch.setattr("coder.server.app.run_session_turn", fake_run_session_turn)

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "follow up"},
    )

    assert response.status_code == 200
    body = response.json()
    assert [message["content"] for message in body["messages"]] == [
        "previous question",
        "previous answer",
        "follow up",
        "new answer",
    ]
