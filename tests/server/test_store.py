from datetime import datetime, timezone

from coder.server.protocol import SessionRecord, SessionStatus
from coder.server.store import SessionStore


def test_save_load_and_list_sessions(tmp_path):
    store = SessionStore(base_dir=tmp_path)
    record = SessionRecord(
        session_id="sess_123",
        status=SessionStatus.idle,
        messages=[],
        created_at=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
    )
    store.save(record)

    loaded = store.load("sess_123")
    assert loaded == record
    assert [s.session_id for s in store.list()] == ["sess_123"]


def test_list_sorts_by_updated_at_descending(tmp_path):
    store = SessionStore(base_dir=tmp_path)
    older = SessionRecord(
        session_id="old",
        status=SessionStatus.idle,
        messages=[],
        created_at=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
    )
    newer = SessionRecord(
        session_id="new",
        status=SessionStatus.running,
        messages=[],
        created_at=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 15, 10, 5, tzinfo=timezone.utc),
    )
    store.save(older)
    store.save(newer)

    assert [s.session_id for s in store.list()] == ["new", "old"]
