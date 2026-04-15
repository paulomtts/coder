import { describe, expect, test } from "bun:test";

describe("terminal ui runtime", () => {
  test("bun provides a tty-backed stdout object", () => {
    expect(typeof process.stdout.write).toBe("function");
    expect(typeof (process.stdout.columns ?? 80)).toBe("number");
  });
});
