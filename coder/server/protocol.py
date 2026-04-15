from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    idle = "idle"
    running = "running"
    cancelled = "cancelled"
    error = "error"


class SessionRecord(BaseModel):
    session_id: str
    status: SessionStatus = SessionStatus.idle
    messages: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cwd: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StreamEvent(BaseModel):
    kind: str
    session_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
