# TUI Scrollback and Auto-Follow Implementation Plan

> **REQUIRED SUB-SKILL:** Use the executing-plans skill to implement this plan task-by-task.

**Goal:** Add proper transcript scrollback to the Bun TUI while keeping auto-follow enabled by default.

**Architecture:** Keep transcript data immutable and add a small UI-only viewport state with `followLatest` and `scrollOffset`. Extract scrolling math into pure helpers so the Ink component stays thin. The TUI will render a computed transcript window, update the viewport on navigation keys, and re-enable auto-follow when the user jumps back to the bottom.

**Tech Stack:** Bun, TypeScript, Ink, React, bun test.

---

### Task 1: Add viewport helpers and unit tests

**Files:**
- Create: `tui/src/viewport.ts`
- Create: `tui/test/viewport.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, test } from "bun:test";
import { computeViewport, handleViewportKey, type ViewportState } from "../src/viewport";

describe("viewport", () => {
  test("keeps the view pinned to the bottom when following latest", () => {
    const state: ViewportState = { followLatest: true, scrollOffset: 0 };
    const result = computeViewport({
      transcriptLength: 8,
      viewportHeight: 3,
      state,
    });

    expect(result.startIndex).toBe(5);
    expect(result.followLatest).toBe(true);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd tui && bun test test/viewport.test.ts`

Expected: FAIL because `viewport.ts` does not exist yet.

**Step 3: Write minimal implementation**

Implement:
- `ViewportState` with `followLatest` and `scrollOffset`
- `computeViewport(...)` to clamp the visible range
- `handleViewportKey(...)` to update scroll state for `PageUp`, `PageDown`, `Home`, `End`, `j`, `k`, and `G`

**Step 4: Run test to verify it passes**

Run: `cd tui && bun test test/viewport.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
git add tui/src/viewport.ts tui/test/viewport.test.ts
git commit -m "feat: add tui viewport helpers"
```

---

### Task 2: Wire the Ink UI to use the viewport helpers

**Files:**
- Modify: `tui/src/App.tsx`
- Modify: `tui/src/view.ts`
- Modify: `tui/src/index.tsx` if needed for full-screen redraw behavior
- Modify: `tui/test/view.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, test } from "bun:test";
import { computeViewport } from "../src/viewport";

describe("viewport integration", () => {
  test("transcript slice follows latest by default", () => {
    const result = computeViewport({
      transcriptLength: 5,
      viewportHeight: 2,
      state: { followLatest: true, scrollOffset: 0 },
    });

    expect(result.startIndex).toBe(3);
    expect(result.endIndex).toBe(5);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd tui && bun test test/view.test.ts`

Expected: FAIL until the viewport helpers are wired into the rendering path.

**Step 3: Write minimal implementation**

Update the TUI so it:
- stores viewport state alongside the transcript
- uses viewport helpers to decide which messages to render
- shows a small status label such as `following latest` or `scrollback`
- responds to navigation keys without breaking message entry

Keep the input prompt behavior unchanged.

**Step 4: Run test to verify it passes**

Run: `cd tui && bun test && bunx tsc -p tsconfig.json --noEmit`

Expected: PASS.

**Step 5: Commit**

```bash
git add tui/src/App.tsx tui/src/view.ts tui/test/view.test.ts
git commit -m "feat: wire tui transcript viewport"
```

---

### Task 3: Verify end-to-end TUI behavior and update docs if needed

**Files:**
- Modify: `README.md`
- Modify: `tui/` files only if a small bug appears during verification

**Step 1: Write the failing test**

No new unit test required; this task is a verification pass.

**Step 2: Run the verification commands**

Run:
- `cd tui && bun test`
- `cd tui && bunx tsc -p tsconfig.json --noEmit`
- `cd tui && bun run dev`

Expected: tests and TypeScript pass; the TUI launches and the transcript pane scrolls when navigation keys are pressed.

**Step 3: Write minimal implementation**

If manual testing finds a rough edge, fix it in the smallest possible way. If behavior is acceptable, update `README.md` to mention the new scrollback controls.

**Step 4: Run the tests to verify they pass**

Run: `cd tui && bun test && bunx tsc -p tsconfig.json --noEmit`

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md tui/src/App.tsx tui/src/viewport.ts tui/src/view.ts tui/test/viewport.test.ts tui/test/view.test.ts
git commit -m "docs: document tui scrollback controls"
```
