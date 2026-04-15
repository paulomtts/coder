# TUI Migration Implementation Plan

> **REQUIRED SUB-SKILL:** Use the executing-plans skill to implement this plan task-by-task.

**Goal:** Replace the current Ink/Bun input path with a real terminal UI architecture that supports live typing, cursor movement, and scrollback, while preserving the current visual style cues (boxed composer, cyan/blue accents, transcript framing).

**Architecture:** Keep the Python FastAPI backend and websocket/session contract intact. Replace the TUI frontend with a real editor/runtime model inspired by OpenCode: a dedicated terminal UI runtime, a live composer component, transcript viewport logic, and styled layout components. The Bun side remains the client/launcher if it still fits the runtime choice, but it must no longer depend on line-buffered stdin or Ink-style `useInput` behavior.

**Tech Stack:** Bun, TypeScript, terminal UI runtime/components, Python FastAPI backend, pytest, bun test.

---

### Task 1: Freeze and verify the current backend/client contract

**Files:**
- Inspect: `coder/server/app.py`
- Inspect: `coder/server/runtime.py`
- Inspect: `coder/server/protocol.py`
- Inspect: `tui/src/api.ts`
- Inspect: `tui/src/bootstrap.ts`
- Inspect: `tui/src/server.ts`

**Step 1: Verify existing tests and behavior**

Run:
- `uv run pytest tests/server -q`
- `cd tui && bun test`
- `cd tui && bunx tsc -p tsconfig.json --noEmit`

**Expected:** baseline passes or any failures are clearly unrelated to the migration scope.

**Step 2: Identify the contract to preserve**

Document the current session lifecycle and event stream assumptions:
- session creation
- server reuse/startup/shutdown
- message submit
- websocket transcript updates
- cancel handling

**Step 3: Do not change backend behavior yet**

The purpose of this task is to lock the contract before replacing the UI stack.

---

### Task 2: Define the new TUI runtime boundaries

**Files:**
- Create: `docs/plans/2026-04-15-tui-runtime-boundary-notes.md` or equivalent short note if needed
- Inspect: current `tui/src/*`

**Step 1: Choose the runtime model**

Use a real terminal UI runtime capable of:
- raw key input
- cursor positioning
- redraws without flicker
- component focus
- boxed regions / panels

**Step 2: Decide what stays and what goes**

Keep:
- transcript data model
- API client
- server bootstrap/reuse logic if still compatible
- view helpers for labels/style logic where reusable

Replace:
- Ink render tree
- `useInput` / stdin line handling
- any prompt logic that depends on line buffering

**Step 3: Define the component surface**

Minimum components:
- header
- status row
- transcript viewport
- composer/editor
- footer/key hints

---

### Task 3: Build the live composer/editor component

**Files:**
- Create/replace: `tui/src/editor/*` or equivalent runtime component files
- Create: tests for composer behavior

**Step 1: Write failing tests for live editing**

Cover:
- typing inserts text immediately
- backspace/delete work
- left/right cursor motion works
- Enter submits the current text
- escape/cancel clears or aborts as designed
- the composer keeps its visible box styling

**Step 2: Implement the composer**

The composer must be a real editor component, not a line reader. It should manage:
- current text
- cursor position
- focus state
- submit callback
- cancel callback if supported

**Step 3: Preserve visual style**

Match the current look and feel:
- blue/cyan bordered input box
- prompt marker / caret styling
- compact padding
- muted helper text below or beside the composer

---

### Task 4: Implement the transcript viewport and auto-follow scrollback

**Files:**
- Create/replace: `tui/src/viewport.ts`
- Update: `tui/src/view.ts`
- Add tests for viewport behavior

**Step 1: Define viewport state**

Track only UI state, not transcript content:
- `followLatest`
- `scrollOffset`
- derived visible range

**Step 2: Write tests**

Cover:
- auto-follow stays pinned on new messages
- scrolling up disables follow mode
- scrolling down returns to the bottom when appropriate
- jump-to-bottom re-enables follow mode
- bounds are clamped

**Step 3: Implement rendering**

The transcript area should:
- remain framed
- show latest messages by default
- allow scrollback while streaming continues
- preserve user/assistant color differentiation

---

### Task 5: Rebuild the screen layout around the new runtime

**Files:**
- Replace: `tui/src/App.tsx` or equivalent root component
- Update: `tui/src/index.tsx`
- Potentially remove/replace: `tui/src/terminal.ts`, `tui/src/input.ts`, old Ink helpers

**Step 1: Write a failing integration/render test**

Verify the screen composition includes:
- app header
- status row
- transcript frame
- composer frame
- footer/hints

**Step 2: Implement the full-screen layout**

Use the runtime’s component model to render the UI regions. The transcript and composer should be separate focusable areas.

**Step 3: Preserve the existing style language**

Keep the UI visually distinct, but consistent with current choices:
- cyan title/header
- gray muted metadata
- bordered transcript and input boxes
- green/magenta role labels
- stable spacing and terminal-native framing

---

### Task 6: Wire keyboard input to transcript actions and composer submission

**Files:**
- Update runtime/input handling files
- Update tests for keybindings and editor integration

**Step 1: Define key behaviors**

Minimum expected behavior:
- printable keys update the composer immediately
- Enter submits
- backspace/delete edit text
- arrows move the cursor
- scroll keys affect transcript viewport only when the transcript is focused or when using dedicated shortcuts
- exit/cancel is handled cleanly

**Step 2: Ensure focus is correct**

The composer should own input focus by default. Transcript scrolling should not steal typing focus unless explicitly intended.

**Step 3: Keep manual command ergonomics simple**

If commands remain, they should be true terminal shortcuts, not a fallback to typed slash commands for basic interaction.

---

### Task 7: Remove the broken Ink path and old line-input code

**Files:**
- Delete or rewrite: `tui/src/App.tsx`, `tui/src/index.tsx`, `tui/src/terminal.ts`, `tui/src/input.ts`, and any now-unused Ink helpers/tests

**Step 1: Remove dead code**

Once the new runtime is working, remove:
- Ink-specific render options
- Bun stdin line reader logic
- line-command fallback UI
- obsolete tests tied to the old interaction model

**Step 2: Update docs**

Revise README usage instructions so they match the new runtime and key behavior.

**Step 3: Keep server/client docs accurate**

The backend startup and session flow should remain documented and unchanged.

---

### Task 8: End-to-end verification

**Files:**
- All changed TUI and docs files

**Step 1: Run verification**

Run:
- `uv run pytest tests/server -q`
- `cd tui && bun test`
- `cd tui && bunx tsc -p tsconfig.json --noEmit`
- manual TUI launch and interaction test

**Step 2: Manual acceptance checklist**

Confirm:
- typing appears live in the composer
- transcript updates stream in correctly
- scrollback works without breaking input focus
- the current style still feels intentional and visually distinct
- server reuse/startup/shutdown still works

**Step 3: Commit in logical chunks**

Prefer small commits for:
- runtime/editor scaffolding
- viewport behavior
- layout/styling
- cleanup/docs

---

## Notes

- This migration is a UI/runtime rewrite, not a backend rewrite.
- Preserve the existing FastAPI contract unless a clear TUI-driven reason requires a backend adjustment.
- Prioritize correctness of input behavior over preserving any current Ink implementation details.
- The styling goal is “same design language, better terminal mechanics,” not a clone of pi-mono or OpenCode.
