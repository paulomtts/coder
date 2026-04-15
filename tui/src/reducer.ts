import type { SessionMessage, SessionStatus, StreamEvent } from "./protocol";

export type TuiState = {
  sessionId: string | null;
  status: SessionStatus;
  transcript: SessionMessage[];
  input: string;
  error: string | null;
};

export const createInitialState = (): TuiState => ({
  sessionId: null,
  status: "idle",
  transcript: [],
  input: "",
  error: null,
});

const appendAssistantText = (
  transcript: SessionMessage[],
  text: string,
): SessionMessage[] => {
  const last = transcript.at(-1);
  if (last?.role === "assistant") {
    return [...transcript.slice(0, -1), { ...last, content: last.content + text }];
  }
  return [...transcript, { role: "assistant", content: text }];
};

export const applyEvent = (state: TuiState, event: StreamEvent): TuiState => {
  switch (event.kind) {
    case "session.created":
      return { ...state, sessionId: String(event.data.session_id ?? state.sessionId) };
    case "message.user_added":
      return {
        ...state,
        transcript: [
          ...state.transcript,
          {
            role: "user",
            content: String(event.data.content ?? ""),
          },
        ],
        status: "running",
      };
    case "assistant.delta":
      return {
        ...state,
        transcript: appendAssistantText(
          state.transcript,
          String(event.data.text ?? ""),
        ),
      };
    case "assistant.completed":
      return { ...state, status: "idle" };
    case "session.error":
      return {
        ...state,
        status: "error",
        error: String(event.data.error ?? "Unknown error"),
      };
    case "session.cancelled":
      return { ...state, status: "cancelled" };
    default:
      return state;
  }
};

export const reduceEvents = (
  initial: TuiState,
  events: StreamEvent[],
): TuiState => events.reduce(applyEvent, initial);
