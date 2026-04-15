import { describe, expect, test } from "bun:test";

import { createInitialState, reduceEvents } from "../src/reducer";

const sessionId = "sess_123";

describe("reduceEvents", () => {
  test("collects user and assistant transcript entries", () => {
    const state = reduceEvents(createInitialState(), [
      {
        kind: "message.user_added",
        session_id: sessionId,
        data: { content: "hello" },
      },
      {
        kind: "assistant.delta",
        session_id: sessionId,
        data: { text: "Hel" },
      },
      {
        kind: "assistant.delta",
        session_id: sessionId,
        data: { text: "lo" },
      },
      {
        kind: "assistant.completed",
        session_id: sessionId,
        data: {},
      },
    ]);

    expect(state.transcript.map((message) => message.content)).toEqual([
      "hello",
      "Hello",
    ]);
    expect(state.status).toBe("idle");
  });
});
