import { describe, expect, test } from "bun:test";

import { parseLineAction } from "../src/input";

describe("parseLineAction", () => {
  test("parses quit and cancel commands", () => {
    expect(parseLineAction("/quit")).toEqual({ type: "quit" });
    expect(parseLineAction("/cancel")).toEqual({ type: "cancel" });
  });

  test("parses scroll commands", () => {
    expect(parseLineAction("/up")).toEqual({ type: "scroll-up" });
    expect(parseLineAction("/down")).toEqual({ type: "scroll-down" });
    expect(parseLineAction("/home")).toEqual({ type: "scroll-home" });
    expect(parseLineAction("/end")).toEqual({ type: "scroll-end" });
  });

  test("treats everything else as a message", () => {
    expect(parseLineAction("Hello there")).toEqual({
      type: "message",
      text: "Hello there",
    });
  });
});
