import { describe, expect, mock, test } from "bun:test";

import { createServerManager } from "../src/server";

describe("createServerManager", () => {
  test("reuses an already healthy server", async () => {
    const fetchFn = mock(async () => new Response(JSON.stringify({ ok: true })));
    const spawnFn = mock(() => {
      throw new Error("should not spawn");
    });
    const manager = createServerManager({
      baseUrl: "http://127.0.0.1:8000",
      fetchFn,
      spawnFn,
      sleepFn: async () => {},
    });

    const result = await manager.ensureServer();

    expect(result.baseUrl).toBe("http://127.0.0.1:8000");
    expect(result.owned).toBe(false);
    expect(spawnFn).not.toHaveBeenCalled();
  });

  test("spawns a server when health check fails and shuts it down later", async () => {
    let healthChecks = 0;
    const fetchFn = mock(async () => {
      healthChecks += 1;
      if (healthChecks < 2) {
        throw new Error("offline");
      }
      return new Response(JSON.stringify({ ok: true }));
    });

    let killed = 0;
    const fakeProcess = {
      kill: () => {
        killed += 1;
      },
      exited: Promise.resolve(0),
    };
    const spawnFn = mock(() => fakeProcess);
    const manager = createServerManager({
      baseUrl: "http://127.0.0.1:8000",
      fetchFn,
      spawnFn,
      sleepFn: async () => {},
    });

    const result = await manager.ensureServer();
    await manager.shutdown();

    expect(result.owned).toBe(true);
    expect(spawnFn).toHaveBeenCalledTimes(1);
    expect(killed).toBeGreaterThan(0);
  });
});
