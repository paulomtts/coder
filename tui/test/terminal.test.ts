import { describe, expect, test } from "bun:test";

import { createInkRenderOptions } from "../src/terminal";

describe("createInkRenderOptions", () => {
  test("uses bun stdio streams", () => {
    const options = createInkRenderOptions();

    const stdin = Bun.stdin as unknown as NodeJS.ReadStream;
    const stdout = process.stdout;
    const stderr = process.stderr;

    expect(options.stdin).toBe(stdin);
    expect(options.stdout).toBe(stdout);
    expect(options.stderr).toBe(stderr);
    expect(options.exitOnCtrlC).toBe(false);
    expect(options.patchConsole).toBe(true);
  });
});
