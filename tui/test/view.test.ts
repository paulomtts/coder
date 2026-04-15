import { describe, expect, test } from "bun:test";

import {
  formatStatusLabel,
  formatViewportLabel,
  renderInputLine,
  visibleTranscript,
} from "../src/view";

describe("view helpers", () => {
  test("formats status labels", () => {
    expect(formatStatusLabel("idle", true, false)).toBe("idle · booting");
    expect(formatStatusLabel("running", false, true)).toBe("running · sending");
  });

  test("formats viewport labels", () => {
    expect(formatViewportLabel(true)).toBe("following latest");
    expect(formatViewportLabel(false)).toBe("scrollback");
  });

  test("renders a prompt line with cursor", () => {
    expect(renderInputLine("hello", true)).toBe("> hello▌");
    expect(renderInputLine("", true)).toContain("Type a message and press Enter");
  });

  test("slices the visible transcript range", () => {
    const transcript = Array.from({ length: 5 }, (_, index) => ({
      role: index % 2 === 0 ? ("user" as const) : ("assistant" as const),
      content: `message-${index}`,
    }));

    expect(visibleTranscript(transcript, 2, 5).map((item) => item.content)).toEqual([
      "message-2",
      "message-3",
      "message-4",
    ]);
  });
});
