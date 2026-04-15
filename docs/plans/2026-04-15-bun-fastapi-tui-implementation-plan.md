# Bun FastAPI TUI Agent Implementation Plan

> **REQUIRED SUB-SKILL:** Use the executing-plans skill to implement this plan task-by-task.

**Goal:** Build a Bun terminal UI that talks to a Python FastAPI agent service with streaming updates, durable sessions, and resume support.

**Architecture:** Keep the existing Python agent runtime as the source of truth. Add a thin FastAPI service that persists sessions, runs the agent, and emits structured stream events. Build the Bun TUI as a client that only renders state, sends user input, and listens to the stream.

**Tech Stack:** Python 3.13, FastAPI, Uvicorn, Pydantic, pytest, Bun, TypeScript, Ink, bun test.

---

### Task 1: Define the wire protocol and session record models

**Files:**
- Create: `coder/server/__init__.py`
- Create: `coder/server/protocol.py`
- Create: `tests/server/test_protocol.py`

**Step 1: Write the failing test**

```python
from coder.server.protocol import SessionRecord, StreamEvent, SessionStatus


def test_session_record_round_trip():
    record = SessionRecord(
        session_id="sess_123",
        status=SessionStatus.idle,
        messages=[{"role": "user", "content": "hi"}],
        created_at="2026-04-15T10:00:00Z",
        updated_at="2026-04-15T10:01:00Z",
    )
    restored = SessionRecord.model_validate(record.model_dump())
    assert restored == record


def test_stream_event_shape():
    event = StreamEvent(kind="assistant.delta", session_id="sess_123", data={"text": "hello"})
    assert event.kind == "assistant.delta"
    assert event.data["text"] == "hello"
```

**Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/server/test_protocol.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'coder.server'` or missing model errors.

**Step 3: Write the minimal implementation**

Implement:
- `SessionStatus` as an enum with `idle`, `running`, `cancelled`, `error`
- `SessionRecord` as a Pydantic model with `session_id`, `status`, `messages`, `created_at`, `updated_at`, and optional metadata like `cwd`
- `StreamEvent` as a Pydantic model with `kind`, `session_id`, `data`, and `timestamp`

Keep the protocol JSON-friendly and stable.

**Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/server/test_protocol.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add coder/server/__init__.py coder/server/protocol.py tests/server/test_protocol.py
git commit -m "feat: define server protocol models"
```

---

### Task 2: Implement JSON session persistence

**Files:**
- Create: `coder/server/store.py`
- Create: `tests/server/test_store.py`
- Modify: `coder/server/protocol.py` if the store needs an extra field such as `last_event_id` or a transcript item model

**Step 1: Write the failing test**

```python
from coder.server.protocol import SessionRecord, SessionStatus
from coder.server.store import SessionStore


def test_save_load_and_list_sessions(tmp_path):
    store = SessionStore(base_dir=tmp_path)
    record = SessionRecord(
        session_id="sess_123",
        status=SessionStatus.idle,
        messages=[],
        created_at="2026-04-15T10:00:00Z",
        updated_at="2026-04-15T10:00:00Z",
    )
    store.save(record)

    loaded = store.load("sess_123")
    assert loaded == record
    assert [s.session_id for s in store.list()] == ["sess_123"]
```

**Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/server/test_store.py -v`

Expected: FAIL because `SessionStore` does not exist yet.

**Step 3: Write the minimal implementation**

Implement `SessionStore` with:
- deterministic session file paths under a base directory
- atomic writes via temp file + rename
- `save(record)`
- `load(session_id)` returning `None` if missing
- `list()` returning records sorted by `updated_at` descending

Use plain JSON files so sessions are easy to inspect and debug.

**Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/server/test_store.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add coder/server/protocol.py coder/server/store.py tests/server/test_store.py
git commit -m "feat: add session persistence store"
```

---

### Task 3: Add the agent runtime bridge and event hooks

**Files:**
- Modify: `coder/agent/loop.py`
- Modify: `coder/agent/hooks.py`
- Create: `coder/server/runtime.py`
- Create: `coder/server/hooks.py`
- Create: `tests/server/test_runtime.py`

**Step 1: Write the failing test**

```python
import pytest
from coder.server.runtime import run_session_turn


@pytest.mark.asyncio
async def test_run_session_turn_emits_assistant_and_tool_events(monkeypatch):
    events = []

    async def emit(event):
        events.append(event.kind)

    # Monkeypatch the runtime so the test can drive a fake agent result.
    # The sequence should include a user message, assistant deltas, and completion.
    await run_session_turn(session_id="sess_123", user_text="hello", emit=emit)

    assert "message.user_added" in events
    assert "assistant.delta" in events
    assert "assistant.completed" in events
```

**Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/server/test_runtime.py -v`

Expected: FAIL because `run_session_turn` and the server hooks do not exist yet.

**Step 3: Write the minimal implementation**

Refactor the agent loop so the server can inject its own after-turn behavior instead of always using console-oriented hooks.

Implement:
- a small event-emitter abstraction in `coder/server/hooks.py`
- a runtime helper in `coder/server/runtime.py` that hydrates the existing agent session from a stored transcript, runs one user turn, and yields `StreamEvent` objects
- a tiny refactor in `coder/agent/loop.py` so `create_agent()` can accept optional extra hooks while preserving the current CLI behavior
- keep `coder/agent/hooks.py` console-friendly for the CLI path, but extract any pure formatting logic that both paths can reuse

Focus on the first usable event set:
- `message.user_added`
- `assistant.delta`
- `tool.started`
- `tool.result`
- `assistant.completed`
- `session.error`
- `session.cancelled`

**Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/server/test_runtime.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add coder/agent/loop.py coder/agent/hooks.py coder/server/runtime.py coder/server/hooks.py tests/server/test_runtime.py
git commit -m "feat: bridge agent runtime into server events"
```

---

### Task 4: Add the FastAPI service and websocket stream

**Files:**
- Create: `coder/server/app.py`
- Create: `coder/server/main.py`
- Modify: `pyproject.toml`
- Create: `tests/server/test_api.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from coder.server.app import create_app


def test_create_session_and_stream():
    client = TestClient(create_app())

    response = client.post("/sessions")
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    with client.websocket_connect(f"/sessions/{session_id}/stream") as ws:
        client.post(f"/sessions/{session_id}/messages", json={"text": "hello"})
        event = ws.receive_json()
        assert event["kind"] in {"message.user_added", "assistant.delta", "assistant.completed"}
```

**Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/server/test_api.py -v`

Expected: FAIL because the FastAPI app is missing and dependencies are not installed yet.

**Step 3: Write the minimal implementation**

Add `fastapi` and `uvicorn` to `pyproject.toml`, then implement:
- `create_app()` in `coder/server/app.py`
- `coder/server/main.py` as the import target for `uvicorn`
- `POST /sessions`
- `GET /sessions/{id}`
- `POST /sessions/{id}/messages`
- `POST /sessions/{id}/cancel`
- `WS /sessions/{id}/stream`

Keep the service thin: route requests to the session store and runtime bridge, then forward `StreamEvent` objects to websocket clients.

**Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/server/test_api.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add coder/server/app.py coder/server/main.py pyproject.toml tests/server/test_api.py
git commit -m "feat: add fastapi session service"
```

---

### Task 5: Scaffold the Bun TUI client

**Files:**
- Create: `tui/package.json`
- Create: `tui/tsconfig.json`
- Create: `tui/src/index.tsx`
- Create: `tui/src/App.tsx`
- Create: `tui/src/api.ts`
- Create: `tui/src/protocol.ts`
- Create: `tui/src/reducer.ts`
- Create: `tui/test/protocol.test.ts`
- Create: `tui/test/reducer.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, test } from "bun:test";
import { reduceEvents } from "../src/reducer";

describe("reduceEvents", () => {
  test("collects assistant deltas into the transcript", () => {
    const state = reduceEvents([], [
      { kind: "assistant.delta", session_id: "sess_123", data: { text: "Hel" } },
      { kind: "assistant.delta", session_id: "sess_123", data: { text: "lo" } },
      { kind: "assistant.completed", session_id: "sess_123", data: {} },
    ]);

    expect(state.transcript.at(-1)?.content).toBe("Hello");
  });
});
```

**Step 2: Run the test to verify it fails**

Run: `bun test`

Expected: FAIL because the Bun app and reducer do not exist yet.

**Step 3: Write the minimal implementation**

Implement the Bun client as a thin terminal UI with Ink:
- `src/api.ts` to call the FastAPI endpoints and open the websocket stream
- `src/protocol.ts` to mirror the Python event/session JSON shapes
- `src/reducer.ts` to fold stream events into renderable UI state
- `src/App.tsx` to render transcript, status, and an input prompt
- `src/index.tsx` to bootstrap the Ink app

Keep the first version small:
- single active session
- resume last session on startup
- render streamed output incrementally
- show offline/error state
- support cancel via a keybinding or button

**Step 4: Run the test to verify it passes**

Run: `bun test`

Expected: PASS.

**Step 5: Commit**

```bash
git add tui/package.json tui/tsconfig.json tui/src/index.tsx tui/src/App.tsx tui/src/api.ts tui/src/protocol.ts tui/src/reducer.ts tui/test/protocol.test.ts tui/test/reducer.test.ts
git commit -m "feat: scaffold bun tui client"
```

---

### Task 6: Update the README with run instructions

**Files:**
- Modify: `README.md`

**Step 1: Write the failing test**

No automated test here; verify the documented commands before editing.

**Step 2: Run the verification commands**

Run:
- `uv run python main.py`
- `uv run uvicorn coder.server.main:app --reload`
- `bun run --cwd tui dev`

Expected: the first command still starts the existing Python CLI, the second starts the FastAPI server, and the third launches the Bun TUI.

**Step 3: Write the minimal documentation update**

Add a short "Run the TUI" section to `README.md` with:
- how to start the Python FastAPI service
- how to start the Bun TUI
- the default local URL used by the client
- a note that sessions persist on disk and can be resumed

**Step 4: Run a quick sanity check**

Run: `uv run pytest -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add bun tui run instructions"
```
