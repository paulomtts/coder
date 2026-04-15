import { describe, expect, mock, test } from "bun:test";

import { startManagedSession } from "../src/bootstrap";

describe("startManagedSession", () => {
  test("connects using the server base url and returns a cleanup function", async () => {
    let disconnected = 0;
    let managerShutdown = 0;
    const manager = {
      ensureServer: mock(async () => ({
        baseUrl: "http://127.0.0.1:8000",
        owned: true,
        shutdown: async () => {
          managerShutdown += 1;
        },
      })),
      shutdown: async () => {
        managerShutdown += 1;
      },
    };

    const api = {
      createSession: mock(async () => ({
        session_id: "sess_123",
        status: "idle" as const,
        messages: [],
      })),
      getSession: mock(async () => {
        throw new Error("unused");
      }),
      sendMessage: mock(async () => ({
        session_id: "sess_123",
        status: "idle" as const,
        messages: [],
      })),
      cancelSession: mock(async () => ({
        session_id: "sess_123",
        status: "idle" as const,
        messages: [],
      })),
      connectSessionStream: mock(() => {
        return () => {
          disconnected += 1;
        };
      }),
    };

    const handle = await startManagedSession({
      manager: manager as never,
      createClient: mock(() => api as never),
    });

    expect(handle.session.session_id).toBe("sess_123");
    expect(api.createSession).toHaveBeenCalledTimes(1);
    expect(api.connectSessionStream).toHaveBeenCalledTimes(1);

    await handle.shutdown();

    expect(disconnected).toBe(1);
    expect(managerShutdown).toBe(1);
  });
});
