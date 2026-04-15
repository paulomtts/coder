import { describe, expect, test } from "bun:test";

import { formatStatusLabel, renderInputLine, visibleTranscript } from "../src/view";

describe("view helpers", () => {
  test("formats status labels", () => {
    expect(formatStatusLabel("idle", true, false)).toBe("idle · booting");
    expect(formatStatusLabel("running", false, true)).toBe("running · sending");
  });

  test("renders a prompt line with cursor", () => {
    expect(renderInputLine("hello", true)).toBe("> hello▌");
    expect(renderInputLine("", true)).toContain("Type a message and press Enter");
  });

  test("only keeps the latest transcript lines", () => {
    const transcript = Array.from({ length: 5 }, (_, index) => ({
      role: index % 2 === 0 ? ("user" as const) : ("assistant" as const),
      content: `message-${index}`,
    }));

    expect(visibleTranscript(transcript, 3).map((item) => item.content)).toEqual([
      "message-2",
      "message-3",
      "message-4",
    ]);
  });
});
