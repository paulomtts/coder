# TUI Starts Python Server Implementation Plan

> **REQUIRED SUB-SKILL:** Use the executing-plans skill to implement this plan task-by-task.

**Goal:** Make the Bun TUI reuse an existing Python FastAPI server when available, otherwise start one as a subprocess and shut it down on exit.

**Architecture:** The TUI owns a tiny server manager. On startup it checks `GET /health`; if the Python server is already healthy it reuses it, otherwise it launches the server subprocess and waits for readiness. The Bun app uses the returned base URL for all API and websocket calls, and only terminates the subprocess if it started one.

**Tech Stack:** Bun, TypeScript, Ink, Python 3.13, FastAPI, uvicorn, pytest, bun test.

---

### Task 1: Add a Python health endpoint

**Files:**
- Modify: `coder/server/app.py:1-190`
- Create: `tests/server/test_health.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from coder.server.app import create_app


def test_health_endpoint_returns_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
```

**Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/server/test_health.py -v`

Expected: FAIL with `404` or missing route.

**Step 3: Write minimal implementation**

Add `GET /health` to the FastAPI app and return `{"ok": True}`.

**Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/server/test_health.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add coder/server/app.py tests/server/test_health.py
git commit -m "feat: add server health endpoint"
```

---

### Task 2: Add a Bun server manager with reuse + subprocess startup

**Files:**
- Create: `tui/src/server.ts`
- Modify: `tui/src/api.ts`
- Create: `tui/test/server.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, mock, test } from "bun:test";
import { createServerManager } from "../src/server";

describe("server manager", () => {
  test("reuses an already healthy server", async () => {
    const fetchMock = mock(async () => new Response(JSON.stringify({ ok: true })));
    const manager = createServerManager({
      baseUrl: "http://127.0.0.1:8000",
      fetchFn: fetchMock,
      spawnFn: async () => {
        throw new Error("should not spawn");
      },
      sleepFn: async () => {},
    });

    const result = await manager.ensureServer();
    expect(result.baseUrl).toBe("http://127.0.0.1:8000");
    expect(result.owned).toBe(false);
  });
});
```

**Step 2: Run the test to verify it fails**

Run: `bun test tui/test/server.test.ts`

Expected: FAIL because `server.ts` does not exist yet.

**Step 3: Write minimal implementation**

Implement a server manager that:
- checks `/health`
- reuses the server if healthy
- otherwise spawns `uv run uvicorn coder.server.main:app --host 127.0.0.1 --port 8000`
- polls `/health` until ready or timeout
- returns `owned = true` only when it spawned the process
- exposes `shutdown()` to terminate owned subprocesses

Refactor `tui/src/api.ts` to accept a `baseUrl` argument or client factory instead of reading a hardcoded global at module load time.

**Step 4: Run the test to verify it passes**

Run: `bun test tui/test/server.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
git add tui/src/server.ts tui/src/api.ts tui/test/server.test.ts
git commit -m "feat: add bun server manager"
```

---

### Task 3: Wire the TUI to own server startup and cleanup

**Files:**
- Modify: `tui/src/App.tsx`
- Modify: `tui/src/index.tsx`
- Create: `tui/test/app-startup.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, mock, test } from "bun:test";
import { createInitialState, applyEvent } from "../src/reducer";

describe("app startup wiring", () => {
  test("applies session.created after server startup", () => {
    const state = applyEvent(createInitialState(), {
      kind: "session.created",
      session_id: "sess_123",
      data: { session_id: "sess_123" },
    });
    expect(state.sessionId).toBe("sess_123");
  });
});
```

**Step 2: Run the test to verify it fails**

Run: `bun test tui/test/app-startup.test.ts`

Expected: likely PASS already, so extend it after wiring to cover startup behavior if needed.

**Step 3: Write minimal implementation**

Update the app so it:
- awaits `ensureServer()` before creating a session
- creates the API client with the returned base URL
- uses the manager’s `shutdown()` in cleanup/unmount
- shows startup errors in the UI if the server cannot be reached or spawned

**Step 4: Run the TUI tests to verify behavior**

Run: `cd tui && bun test && bunx tsc -p tsconfig.json --noEmit`

Expected: PASS.

**Step 5: Commit**

```bash
git add tui/src/App.tsx tui/src/index.tsx tui/test/app-startup.test.ts
git commit -m "feat: wire tui server lifecycle"
```

---

### Task 4: Add a lightweight uvicorn app entrypoint and update docs

**Files:**
- Create: `coder/server/main.py`
- Modify: `README.md`

**Step 1: Write the failing test**

No additional test required beyond the health endpoint and startup tests; verify the entrypoint manually.

**Step 2: Run the verification command**

Run: `uv run uvicorn coder.server.main:app --host 127.0.0.1 --port 8000`

Expected: server starts and responds to `GET /health`.

**Step 3: Write minimal implementation**

Expose `app = create_app()` in `coder/server/main.py` so the Bun TUI has a stable subprocess target.

Update `README.md` to document that the Bun TUI can now auto-start the Python service and reuse an existing one.

**Step 4: Run a final sanity check**

Run:
- `uv run pytest tests/server -q`
- `cd tui && bun test`

Expected: PASS.

**Step 5: Commit**

```bash
git add coder/server/main.py README.md
git commit -m "docs: document tui-managed server startup"
```
