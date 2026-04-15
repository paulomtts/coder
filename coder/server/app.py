from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from coder.agent.session import Session
from coder.agent.state import set_session
from coder.server.protocol import SessionRecord, SessionStatus, StreamEvent
from coder.server.runtime import run_session_turn
from coder.server.store import SessionStore
from pygents import ContextItem


class SessionCreateRequest(BaseModel):
    cwd: str | None = None


class MessageRequest(BaseModel):
    text: str = Field(min_length=1)


@dataclass
class SessionEntry:
    record: SessionRecord
    session: Session | None = None
    listeners: list[asyncio.Queue[StreamEvent]] = field(default_factory=list)


class SessionHub:
    def __init__(self, store: SessionStore):
        self.store = store
        self.entries: dict[str, SessionEntry] = {}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _cache_record(self, record: SessionRecord) -> SessionEntry:
        entry = self.entries.get(record.session_id)
        if entry is None:
            entry = SessionEntry(record=record)
            self.entries[record.session_id] = entry
        else:
            entry.record = record
        return entry

    async def create_session(self, cwd: str | None = None) -> SessionRecord:
        session_id = uuid.uuid4().hex
        now = self._now()
        record = SessionRecord(
            session_id=session_id,
            status=SessionStatus.idle,
            messages=[],
            created_at=now,
            updated_at=now,
            cwd=cwd,
        )
        self.store.save(record)
        self._cache_record(record)
        return record

    def get_record(self, session_id: str) -> SessionRecord | None:
        entry = self.entries.get(session_id)
        if entry is not None:
            return entry.record
        record = self.store.load(session_id)
        if record is None:
            return None
        return self._cache_record(record).record

    async def get_or_create_record(self, session_id: str) -> SessionRecord:
        record = self.get_record(session_id)
        if record is not None:
            return record
        now = self._now()
        record = SessionRecord(
            session_id=session_id,
            status=SessionStatus.idle,
            messages=[],
            created_at=now,
            updated_at=now,
        )
        self.store.save(record)
        self._cache_record(record)
        return record

    async def ensure_session(self, session_id: str) -> Session:
        entry = self.entries.get(session_id)
        if entry is None:
            record = await self.get_or_create_record(session_id)
            entry = self._cache_record(record)

        if entry.session is None:
            session = Session()
            await session.start(cwd=entry.record.cwd)
            set_session(session)
            for message in entry.record.messages:
                await session.cq.append(ContextItem(content=message))
            entry.session = session
        return entry.session

    async def broadcast(self, session_id: str, event: StreamEvent) -> None:
        entry = self.entries.get(session_id)
        if entry is None:
            return
        for queue in list(entry.listeners):
            await queue.put(event)

    async def add_listener(self, session_id: str) -> asyncio.Queue[StreamEvent]:
        entry = self._cache_record(await self.get_or_create_record(session_id))
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue()
        entry.listeners.append(queue)
        return queue

    def remove_listener(self, session_id: str, queue: asyncio.Queue[StreamEvent]) -> None:
        entry = self.entries.get(session_id)
        if entry is None:
            return
        if queue in entry.listeners:
            entry.listeners.remove(queue)

    def save(self, record: SessionRecord) -> None:
        record.updated_at = self._now()
        self.store.save(record)
        self._cache_record(record)


def create_app(base_dir: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Coder Agent Service")
    store = SessionStore(base_dir or Path.home() / ".coder" / "sessions")
    hub = SessionHub(store)
    app.state.store = store
    app.state.hub = hub

    @app.post("/sessions", response_model=SessionRecord)
    async def create_session(payload: SessionCreateRequest | None = None) -> SessionRecord:
        cwd = payload.cwd if payload else None
        return await hub.create_session(cwd=cwd)

    @app.get("/sessions/{session_id}", response_model=SessionRecord)
    async def get_session(session_id: str) -> SessionRecord:
        record = hub.get_record(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return record

    @app.post("/sessions/{session_id}/messages", response_model=SessionRecord)
    async def post_message(session_id: str, payload: MessageRequest) -> SessionRecord:
        record = await hub.get_or_create_record(session_id)
        session = await hub.ensure_session(session_id)
        record.status = SessionStatus.running
        record.updated_at = hub._now()
        record.messages.append({"role": "user", "content": payload.text})
        hub.save(record)

        async def emit(event: StreamEvent) -> None:
            await hub.broadcast(session_id, event)

        result = await run_session_turn(
            session_id=session_id,
            user_text=payload.text,
            emit=emit,
            cwd=record.cwd,
            session=session,
        )
        result.created_at = record.created_at
        result.cwd = record.cwd
        result.metadata = record.metadata
        result.messages = record.messages + result.messages[1:]
        hub.save(result)
        return result

    @app.post("/sessions/{session_id}/cancel", response_model=SessionRecord)
    async def cancel_session(session_id: str) -> SessionRecord:
        record = await hub.get_or_create_record(session_id)
        record.status = SessionStatus.cancelled
        hub.save(record)
        await hub.broadcast(
            session_id,
            StreamEvent(kind="session.cancelled", session_id=session_id, data={}),
        )
        return record

    @app.websocket("/sessions/{session_id}/stream")
    async def session_stream(websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        queue = await hub.add_listener(session_id)
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event.model_dump(mode="json"))
        except WebSocketDisconnect:
            pass
        finally:
            hub.remove_listener(session_id, queue)

    return app
