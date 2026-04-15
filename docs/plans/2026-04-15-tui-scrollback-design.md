# TUI Scrollback and Auto-Follow Design

Date: 2026-04-15

## Summary

The Bun TUI currently renders a fixed slice of the latest transcript messages. This design upgrades it to a proper chat-style viewport with **auto-follow by default** and **manual scrollback** when the user navigates away from the bottom.

The transcript remains the source of truth. The UI only tracks viewport state: whether it is following the latest message, and how far it is scrolled away from the newest content. This keeps scrolling behavior isolated from session data and agent logic.

The goal is a lightweight terminal UX that feels like a chat app without adding a full text editor or complex terminal widget stack.

---

## Goals

- Always show the latest transcript by default.
- Allow users to scroll back through prior messages while the agent continues running.
- Re-enable auto-follow when the user jumps back to the bottom.
- Keep the implementation small and testable.
- Preserve the current simple input prompt.

## Non-Goals

- Search within transcript history.
- Mouse-driven scrolling.
- Persisting scroll position across restarts.
- Multi-pane layouts or rich markdown rendering.

---

## Architecture

### State Model

The TUI state should gain a small viewport section:

- `followLatest: boolean`
- `scrollOffset: number`

The transcript itself remains unchanged. The viewport helpers compute the visible slice based on transcript length and an approximate pane height. The UI does not mutate transcript order or trim older messages.

### Rendering Model

The app will keep the existing three-region layout:

1. header and status
2. scrollable transcript pane
3. input prompt and key hints

The transcript pane will render a computed slice instead of the fixed last-N messages. When `followLatest` is true, the viewport sticks to the bottom. When the user scrolls upward, `followLatest` turns off and the viewport stays pinned to the chosen range until the user jumps back to the bottom.

### Interaction Model

Suggested keys:

- `PageUp` / `k` → scroll up
- `PageDown` / `j` → scroll down
- `Home` → jump to oldest message
- `End` / `G` → jump to newest message and resume follow mode

When new transcript entries arrive:
- if `followLatest` is true, the viewport stays pinned to the bottom
- if `followLatest` is false, the viewport does not move

This gives the user a stable reading experience while the agent continues streaming output.

---

## Data Flow

1. The agent stream appends transcript messages to state.
2. Viewport helpers compute the visible window from transcript length and scroll state.
3. The React/Ink component renders that window in the transcript pane.
4. Navigation keys update viewport state only.
5. Jump-to-bottom restores `followLatest = true`.

This keeps scrolling orthogonal to message handling and makes it easy to test.

---

## Error Handling

Scrolling logic should be bounded:

- never scroll above the oldest message
- never scroll below the newest message
- if the transcript becomes shorter than the viewport, clamp the offset to zero

If the transcript is empty, the UI should show a simple placeholder such as “Waiting for the first message...”.

---

## Testing

Add unit tests for the viewport helpers:

- auto-follow stays pinned on new messages
- scrolling up disables follow mode
- jumping to the bottom re-enables follow mode
- viewport bounds are clamped correctly
- visible transcript slice is computed consistently

The React component itself should stay thin; the logic belongs in pure helpers so it can be tested without terminal integration.
