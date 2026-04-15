from datetime import datetime, timezone

from coder.server.protocol import SessionRecord, SessionStatus, StreamEvent


def test_session_record_round_trip():
    record = SessionRecord(
        session_id="sess_123",
        status=SessionStatus.idle,
        messages=[{"role": "user", "content": "hi"}],
        created_at=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 15, 10, 1, tzinfo=timezone.utc),
    )
    restored = SessionRecord.model_validate(record.model_dump())
    assert restored == record


def test_stream_event_shape():
    event = StreamEvent(
        kind="assistant.delta",
        session_id="sess_123",
        data={"text": "hello"},
    )
    assert event.kind == "assistant.delta"
    assert event.data["text"] == "hello"
