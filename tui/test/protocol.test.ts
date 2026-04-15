import { describe, expect, test } from "bun:test";

import type { SessionRecord, StreamEvent } from "../src/protocol";

describe("protocol", () => {
  test("session record shape", () => {
    const record: SessionRecord = {
      session_id: "sess_123",
      status: "idle",
      messages: [{ role: "user", content: "hi" }],
    };

    expect(record.session_id).toBe("sess_123");
    expect(record.messages[0].content).toBe("hi");
  });

  test("stream event shape", () => {
    const event: StreamEvent = {
      kind: "assistant.delta",
      session_id: "sess_123",
      data: { text: "hello" },
    };

    expect(event.data.text).toBe("hello");
  });
});
