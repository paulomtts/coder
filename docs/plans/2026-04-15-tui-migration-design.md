# TUI Migration Design

Date: 2026-04-15

## Summary

The current Bun TUI path is built on Ink, but the terminal input experience is not acceptable for a real agent interface: live typing, cursor movement, and the prompt area do not behave like a terminal editor. This migration replaces the current Ink-based input layer with a real TUI architecture while preserving the existing backend and the current visual language.

The backend remains unchanged in spirit: Python/FastAPI continues to own sessions, persistence, agent execution, and websocket event streaming. The TUI continues to be a client of that backend over HTTP + WebSocket. The main change is that the UI layer becomes a proper terminal app with direct keyboard input, instead of a line-buffered or React-rendered approximation.

The design goal is not to copy pi-mono or OpenCode exactly. Instead, we keep the current product shape — transcript panel, boxed composer, distinct color accents, and auto-follow/scrollback behavior — while swapping in an input/runtime model that can actually support live editing.

---

## Recommended Approach

Use an OpenCode-style architecture as the reference model:

- a dedicated terminal runtime
- a real input/editor component
- a render loop that owns the full-screen layout
- UI widgets for transcript, composer, header, footer, and modal states

This is the best tradeoff for this repo because it is interactive enough to feel like a real terminal app, but less low-level than building a terminal engine from scratch.

### Why this approach

- It supports live typing and cursor behavior.
- It gives us a structured place to preserve the current styling choices.
- It avoids continuing to fight Ink’s assumptions.
- It keeps the migration manageable compared to a full pi-mono-style engine rewrite.

### Alternatives considered

1. **pi-mono-style custom terminal engine**
   - Pros: maximum control, lowest abstraction leakage
   - Cons: much more work, more risk, more terminal-specific code to maintain

2. **OpenCode-style TUI runtime**
   - Pros: real editor behavior, composable UI, maintainable architecture
   - Cons: still a rewrite of the UI layer, some new runtime concepts to learn

3. **Keep Ink and patch around Bun input**
   - Pros: least code churn
   - Cons: does not solve the core UX problem; current failure mode remains

Recommendation: **OpenCode-style runtime**.

---

## Architecture

### Layering

The system should be split into three layers:

1. **Python backend**
   - FastAPI server
   - session store and agent execution
   - HTTP endpoints for session creation and control
   - websocket stream for transcript events

2. **TUI transport/client layer**
   - connection management
   - server reuse/startup/shutdown behavior
   - websocket event subscription
   - request/response calls for session actions

3. **TUI runtime/UI layer**
   - direct keyboard input handling
   - prompt/editor state
   - transcript viewport and scrolling
   - header/status/footer rendering
   - boxed composer and visual styling

### Core UI regions

The screen should remain structured as:

- **Header**: app name, session id, connection state
- **Status row**: run state, follow/scroll state, short hints
- **Transcript panel**: scrollable messages and streaming assistant output
- **Composer box**: boxed input area with live typing
- **Footer row**: compact key hints or mode indicator

The transcript panel should remain the source of truth for visible conversation history. The composer should be a real editor component, not a line reader.

### Input model

The composer must support:

- live character insertion
- backspace/delete
- left/right cursor movement
- submit on Enter
- optional cancel/escape
- future multiline support if needed

The exact key bindings can mirror standard terminal editor behavior, but the important point is that input is handled as raw terminal events, not buffered lines.

---

## Visual Design

The current visual language should be preserved but refined:

- a **boxed composer** with a blue or cyan border
- **cyan title** in the header
- muted gray status/footer text
- green for user messages
- magenta for assistant messages
- framed transcript viewport with a visible scroll state
- minimal, terminal-native spacing

The intent is to keep the UI feeling like our product, not like a generic cloned TUI. The new runtime should allow the same palette and framing, but with more reliable input rendering.

Suggested style directions:

- transcript box: gray border, subtle background emphasis if supported
- input box: blue border when idle, brighter accent when focused or active
- status rows: dim text, low visual noise
- messages: colored role label plus white content
- error states: red accent, but keep the layout stable

---

## Data Flow

1. The TUI boots and connects to the backend, reusing an already-running server when possible.
2. The backend creates or resumes a session.
3. WebSocket events append to the transcript state.
4. The render loop redraws the transcript and input regions.
5. Keyboard input updates the composer state immediately.
6. On submit, the composer text is sent to the backend as a message.
7. Transcript scroll state stays separate from transcript data.

This keeps session data on the Python side and UI state on the terminal side.

---

## Migration Scope

### Keep

- Python FastAPI backend
- session lifecycle and persistence logic
- websocket streaming protocol
- server reuse/startup/shutdown behavior
- high-level terminal app structure

### Replace

- Ink renderer usage
- line-buffered stdin input handling
- current `useInput`/React-centric composition model
- any prompt logic that relies on typed text only appearing after Enter

### Rework

- transcript rendering into a real viewport widget
- composer implementation into a live editor
- key handling and focus management
- styling helpers for the new runtime

---

## Error Handling

The TUI should handle failures in a stable, visible way:

- backend unavailable: show a clear connection/error state
- websocket disconnect: show disconnected or retrying state
- session creation failure: show error without breaking the whole screen
- message send failure: keep the composer intact and display the error inline
- input/runtime failure: restore terminal state cleanly on exit

The UI should never fall back to raw stack traces as the primary user experience.

---

## Testing

The migration should be validated at three levels:

1. **Pure unit tests**
   - composer input state transitions
   - transcript viewport calculations
   - layout and style helper output

2. **Client integration tests**
   - server reuse vs startup behavior
   - message send and event stream handling
   - cancel/shutdown flow

3. **Manual terminal verification**
   - live typing appears as typed
   - scrollback does not break transcript following
   - composer and transcript remain visually stable during streaming

A successful migration must prove that the prompt area behaves like a real terminal editor and that the transcript remains usable while responses stream in.

---

## Rollout Plan

1. Freeze the current backend contract.
2. Introduce the new TUI runtime alongside the existing implementation.
3. Port transcript rendering first.
4. Port composer/input next.
5. Add scrollback and follow-latest behavior.
6. Remove the old Ink-based path once the new runtime is verified.
7. Update documentation and examples.

This staged approach reduces risk and lets us validate the new UX incrementally.
