import { createApiClient, type ApiClient } from "./api";
import { createServerManager, type ServerManager } from "./server";
import type { SessionRecord, StreamEvent } from "./protocol";

export type TuiSessionHandle = {
  api: ApiClient;
  session: SessionRecord;
  shutdown: () => Promise<void>;
};

export type BootstrapOptions = {
  manager?: ServerManager;
  createClient?: (baseUrl: string) => ApiClient;
  onEvent?: (event: StreamEvent) => void;
};

export async function startManagedSession(
  options: BootstrapOptions = {},
): Promise<TuiSessionHandle> {
  const manager = options.manager ?? createServerManager();
  const createClient = options.createClient ?? createApiClient;
  const server = await manager.ensureServer();
  const api = createClient(server.baseUrl);
  const session = await api.createSession();
  const disconnect = api.connectSessionStream(session.session_id, (event) => {
    options.onEvent?.(event);
  });

  return {
    api,
    session,
    shutdown: async () => {
      disconnect();
      await manager.shutdown();
    },
  };
}
