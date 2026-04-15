import path from "node:path";

const DEFAULT_BASE_URL = process.env.CODER_API_URL ?? "http://127.0.0.1:8000";
const DEFAULT_COMMAND = [
  "uv",
  "run",
  "uvicorn",
  "coder.server.main:app",
  "--host",
  "127.0.0.1",
  "--port",
  "8000",
];

export type ManagedProcess = {
  kill: (signal?: number | string) => void;
  exited: Promise<unknown>;
};

export type SpawnFn = (command: string[]) => ManagedProcess;
export type FetchFn = (input: string | URL, init?: RequestInit) => Promise<Response>;
export type SleepFn = (ms: number) => Promise<void>;

export type ServerHandle = {
  baseUrl: string;
  owned: boolean;
  shutdown: () => Promise<void>;
};

export type ServerManager = {
  ensureServer: () => Promise<ServerHandle>;
  shutdown: () => Promise<void>;
};

export type ServerManagerOptions = {
  baseUrl?: string;
  command?: string[];
  fetchFn?: FetchFn;
  spawnFn?: SpawnFn;
  sleepFn?: SleepFn;
  healthTimeoutMs?: number;
  pollIntervalMs?: number;
};

const REPO_ROOT = path.resolve(import.meta.dir, "../..");

const defaultSleep: SleepFn = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function isHealthy(baseUrl: string, fetchFn: FetchFn): Promise<boolean> {
  try {
    const response = await fetchFn(`${baseUrl}/health`);
    if (!response.ok) return false;
    const payload = (await response.json()) as { ok?: unknown };
    return payload.ok === true;
  } catch {
    return false;
  }
}

function defaultSpawn(command: string[]): ManagedProcess {
  const process = Bun.spawn({
    cmd: command,
    cwd: REPO_ROOT,
    stdout: "inherit",
    stderr: "inherit",
    stdin: "inherit",
  });
  return {
    kill: (signal?: number | string) => {
      process.kill(signal as never);
    },
    exited: process.exited,
  };
}

export function createServerManager(
  options: ServerManagerOptions = {},
): ServerManager {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const command = options.command ?? DEFAULT_COMMAND;
  const fetchFn = options.fetchFn ?? fetch;
  const spawnFn = options.spawnFn ?? defaultSpawn;
  const sleepFn = options.sleepFn ?? defaultSleep;
  const healthTimeoutMs = options.healthTimeoutMs ?? 15_000;
  const pollIntervalMs = options.pollIntervalMs ?? 250;

  let owned = false;
  let process: ManagedProcess | null = null;
  let started = false;

  const shutdown = async (): Promise<void> => {
    if (!owned || process === null) return;
    try {
      process.kill();
    } catch {
      // Ignore termination errors.
    }

    const result = await Promise.race([
      process.exited.then(() => "exited" as const),
      sleepFn(2_000).then(() => "timeout" as const),
    ]);

    if (result === "timeout") {
      try {
        process.kill(9 as never);
      } catch {
        // Ignore hard-kill errors.
      }
      try {
        await process.exited;
      } catch {
        // Ignore exit rejections.
      }
    }
  };

  const ensureServer = async (): Promise<ServerHandle> => {
    if (started) {
      return { baseUrl, owned, shutdown };
    }

    if (await isHealthy(baseUrl, fetchFn)) {
      started = true;
      owned = false;
      return { baseUrl, owned, shutdown };
    }

    process = spawnFn(command);
    owned = true;
    started = true;

    const deadline = Date.now() + healthTimeoutMs;
    while (Date.now() < deadline) {
      if (await isHealthy(baseUrl, fetchFn)) {
        return { baseUrl, owned, shutdown };
      }
      await sleepFn(pollIntervalMs);
    }

    throw new Error(`Timed out waiting for Python server at ${baseUrl}`);
  };

  return { ensureServer, shutdown };
}
