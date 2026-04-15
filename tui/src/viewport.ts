export type ViewportState = {
  followLatest: boolean;
  scrollOffset: number;
};

export type ViewportComputation = {
  startIndex: number;
  endIndex: number;
  followLatest: boolean;
  scrollOffset: number;
  maxScrollOffset: number;
};

export type ViewportKey = {
  pageUp?: boolean;
  pageDown?: boolean;
  upArrow?: boolean;
  downArrow?: boolean;
};

export type ViewportInput = {
  transcriptLength: number;
  viewportHeight: number;
  state: ViewportState;
};

const clamp = (value: number, min: number, max: number): number =>
  Math.max(min, Math.min(max, value));

export const createViewportState = (): ViewportState => ({
  followLatest: true,
  scrollOffset: 0,
});

export function computeViewport({
  transcriptLength,
  viewportHeight,
  state,
}: ViewportInput): ViewportComputation {
  const maxScrollOffset = Math.max(0, transcriptLength - viewportHeight);
  const scrollOffset = clamp(state.scrollOffset, 0, maxScrollOffset);
  const effectiveOffset = state.followLatest ? 0 : scrollOffset;
  const startIndex = clamp(
    transcriptLength - viewportHeight - effectiveOffset,
    0,
    maxScrollOffset,
  );
  const endIndex = Math.min(transcriptLength, startIndex + viewportHeight);

  return {
    startIndex,
    endIndex,
    followLatest: state.followLatest,
    scrollOffset: effectiveOffset,
    maxScrollOffset,
  };
}

export function scrollUp(
  state: ViewportState,
  transcriptLength: number,
  viewportHeight: number,
  amount = 1,
): ViewportState {
  const maxScrollOffset = Math.max(0, transcriptLength - viewportHeight);
  return {
    followLatest: false,
    scrollOffset: clamp(state.scrollOffset + amount, 0, maxScrollOffset),
  };
}

export function scrollDown(
  state: ViewportState,
  transcriptLength: number,
  viewportHeight: number,
  amount = 1,
): ViewportState {
  const maxScrollOffset = Math.max(0, transcriptLength - viewportHeight);
  const nextOffset = clamp(state.scrollOffset - amount, 0, maxScrollOffset);
  return {
    followLatest: nextOffset === 0,
    scrollOffset: nextOffset,
  };
}

export function jumpToOldest(
  transcriptLength: number,
  viewportHeight: number,
): ViewportState {
  return {
    followLatest: false,
    scrollOffset: Math.max(0, transcriptLength - viewportHeight),
  };
}

export function jumpToLatest(): ViewportState {
  return {
    followLatest: true,
    scrollOffset: 0,
  };
}

export function handleViewportKey(
  state: ViewportState,
  key: ViewportKey,
  transcriptLength: number,
  viewportHeight: number,
): ViewportState {
  if (key.pageUp) return scrollUp(state, transcriptLength, viewportHeight, viewportHeight - 1 || 1);
  if (key.pageDown) return scrollDown(state, transcriptLength, viewportHeight, viewportHeight - 1 || 1);
  if (key.upArrow) return scrollUp(state, transcriptLength, viewportHeight, 1);
  if (key.downArrow) return scrollDown(state, transcriptLength, viewportHeight, 1);
  return state;
}
