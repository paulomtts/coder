import { describe, expect, test } from "bun:test";

import {
  computeViewport,
  createViewportState,
  handleViewportKey,
  jumpToLatest,
  jumpToOldest,
  scrollDown,
  scrollUp,
} from "../src/viewport";

describe("viewport", () => {
  test("keeps the view pinned to the bottom when following latest", () => {
    const state = createViewportState();
    const result = computeViewport({
      transcriptLength: 8,
      viewportHeight: 3,
      state,
    });

    expect(result.startIndex).toBe(5);
    expect(result.endIndex).toBe(8);
    expect(result.followLatest).toBe(true);
  });

  test("scrolling up disables follow mode and moves the window back", () => {
    const state = scrollUp(createViewportState(), 10, 4, 2);
    const result = computeViewport({
      transcriptLength: 10,
      viewportHeight: 4,
      state,
    });

    expect(state.followLatest).toBe(false);
    expect(state.scrollOffset).toBe(2);
    expect(result.startIndex).toBe(4);
  });

  test("scrolling down returns to follow mode at the bottom", () => {
    const state = scrollDown({ followLatest: false, scrollOffset: 2 }, 10, 4, 2);
    const result = computeViewport({
      transcriptLength: 10,
      viewportHeight: 4,
      state,
    });

    expect(state.followLatest).toBe(true);
    expect(result.startIndex).toBe(6);
  });

  test("jump helpers clamp to bounds", () => {
    expect(jumpToOldest(3, 10)).toEqual({ followLatest: false, scrollOffset: 0 });
    expect(jumpToLatest()).toEqual({ followLatest: true, scrollOffset: 0 });
  });

  test("handleViewportKey supports navigation keys", () => {
    const afterPageUp = handleViewportKey(createViewportState(), { pageUp: true }, 12, 4);
    const afterPageDown = handleViewportKey(afterPageUp, { pageDown: true }, 12, 4);
    const afterUp = handleViewportKey(afterPageDown, { upArrow: true }, 12, 4);
    const afterDown = handleViewportKey(afterUp, { downArrow: true }, 12, 4);

    expect(afterPageUp.followLatest).toBe(false);
    expect(afterPageUp.scrollOffset).toBe(3);
    expect(afterPageDown.followLatest).toBe(true);
    expect(afterPageDown.scrollOffset).toBe(0);
    expect(afterUp.followLatest).toBe(false);
    expect(afterUp.scrollOffset).toBe(1);
    expect(afterDown.followLatest).toBe(true);
    expect(afterDown.scrollOffset).toBe(0);
  });
});
