import type { SessionMessage, SessionStatus } from "./protocol";

export function formatStatusLabel(
  status: SessionStatus,
  isBooting: boolean,
  isSending: boolean,
): string {
  const parts: string[] = [status];
  if (isBooting) parts.push("booting");
  if (isSending) parts.push("sending");
  return parts.join(" · ");
}

export function formatViewportLabel(followLatest: boolean): string {
  return followLatest ? "following latest" : "scrollback";
}

export function visibleTranscript(
  transcript: SessionMessage[],
  startIndex: number,
  endIndex: number,
): SessionMessage[] {
  return transcript.slice(startIndex, endIndex);
}

export function renderComposerLine(draft: string, cursor: number): string {
  const before = draft.slice(0, cursor);
  const after = draft.slice(cursor);
  return `> ${before}▌${after}`.trimEnd();
}
