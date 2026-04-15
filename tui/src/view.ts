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

export function renderInputLine(
  draft: string,
  isFocused: boolean,
): string {
  const cursor = isFocused ? "▌" : "";
  return draft.length > 0 ? `> ${draft}${cursor}` : `> ${isFocused ? cursor : ""}Type a message and press Enter`;
}

export function visibleTranscript(
  transcript: SessionMessage[],
  startIndex: number,
  endIndex: number,
): SessionMessage[] {
  return transcript.slice(startIndex, endIndex);
}
