# TUI-Managed Python Server Design

Date: 2026-04-15

## Summary

This design extends the Bun TUI so it can reuse an already-running Python FastAPI server, or start one itself when needed. The TUI becomes the process owner only when it launches the server subprocess. If a server is already reachable, the TUI simply connects and does not interfere with lifecycle management.

This keeps the app ergonomic for local use:
- start the TUI only, and it can bootstrap everything it needs
- run the Python service separately, and the TUI will attach to it
- exit the TUI, and any subprocess it started will be shut down cleanly

The Python service remains the source of truth for sessions, persistence, and agent execution. The Bun side only manages process lifecycle and UI connectivity.

---

## Goals

- Reuse an already-running Python server when available.
- Start the Python server automatically when none is running.
- Cleanly shut down only the server subprocess started by the TUI.
- Keep the feature local-first and simple.
- Add a small readiness check so startup is deterministic.

## Non-Goals

- Multi-instance orchestration.
- Automatic server restarts.
- Remote discovery of Python services.
- Distributed or networked lifecycle management.

---

## Architecture

### Components

- **Bun TUI**
  - Owns terminal rendering and input handling.
  - Contains a small server manager.
  - Connects to the Python API and stream endpoints.

- **Bun Server Manager**
  - Resolves the base API URL.
  - Checks whether the Python server is already healthy.
  - Starts the Python server subprocess if needed.
  - Tracks whether the TUI owns the subprocess.
  - Terminates the subprocess on exit if it was started by the TUI.

- **Python FastAPI Service**
  - Owns session persistence and agent execution.
  - Exposes the health check endpoint.
  - Remains usable independently of the TUI.

### Ownership Model

The key state is whether the TUI **owns** the server process.

- `owned = false`: an external server is already running; the TUI must not shut it down.
- `owned = true`: the TUI started the server and is responsible for cleanup.

This distinction is stored in the server manager only and never leaks into session logic.

---

## Startup Flow

1. The TUI resolves `CODER_API_URL` or defaults to `http://127.0.0.1:8000`.
2. The server manager calls `GET /health`.
3. If the health check succeeds, the TUI connects immediately and marks the server as external.
4. If the health check fails, the TUI starts the Python subprocess.
5. The manager polls `/health` until the server becomes ready or a timeout is reached.
6. Once ready, the TUI continues startup and marks the process as owned.
7. The UI uses the same base URL for session and stream endpoints regardless of whether the server was external or spawned locally.

This gives a single startup path from the UI’s perspective while still supporting both runtime modes.

---

## Python Contract

Add a minimal readiness endpoint:

- `GET /health -> { "ok": true }`

That endpoint should not depend on any session state. It should be quick and safe to call repeatedly while the TUI waits for startup.

For the subprocess command, the TUI should use a non-reload command suitable for ownership. Reload mode can remain documented for manual development runs, but the TUI-owned child process should be simple to track and terminate.

---

## Cleanup Flow

When the TUI exits:

1. Close the WebSocket stream.
2. Cancel any in-flight requests when possible.
3. If the server manager says `owned = true`, send a graceful termination signal to the subprocess.
4. Wait briefly for the process to exit.
5. Force kill only if the process remains alive.

If the server was external, cleanup is a no-op beyond closing client connections.

This avoids accidentally terminating a user-managed server while still keeping the automatic mode tidy.

---

## Error Handling

Startup failures should be surfaced clearly in the TUI:

- Python executable missing
- server command failed immediately
- health check timed out
- external server became unavailable mid-session

If the server fails after startup, the UI should show a normal service error state and stop relying on the stream. It should not attempt to repeatedly relaunch the server in the background; that would make failures harder to understand.

The primary user-visible distinction is simple:
- **could not start** → startup error
- **started but later died** → service error while running

---

## Testing Strategy

### Bun Tests

- returns immediately when `/health` succeeds
- spawns the Python subprocess when `/health` fails
- sets `owned = true` only for spawned processes
- does not kill external servers on shutdown
- kills owned subprocesses on shutdown
- propagates startup timeout errors clearly

These tests should mock `Bun.spawn()` and the health polling path.

### Python Tests

- `GET /health` returns `{ "ok": true }`
- health endpoint does not require session state

The health test should be small and isolated.

---

## Recommended Implementation Order

1. Add the Python `/health` endpoint and test.
2. Add the Bun server manager with health probing.
3. Wire the TUI to call `ensureServer()` on startup.
4. Wire cleanup so owned subprocesses are terminated on exit.
5. Add tests for reuse, spawn, and cleanup behavior.

This keeps the feature small and ensures the TUI can run standalone without requiring manual Python startup.
