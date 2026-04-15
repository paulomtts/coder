import type { SessionRecord, StreamEvent } from "./protocol";

export type ApiClient = {
  createSession: (cwd?: string) => Promise<SessionRecord>;
  getSession: (sessionId: string) => Promise<SessionRecord>;
  sendMessage: (sessionId: string, text: string) => Promise<SessionRecord>;
  cancelSession: (sessionId: string) => Promise<SessionRecord>;
  connectSessionStream: (
    sessionId: string,
    onEvent: (event: StreamEvent) => void,
    onError?: (error: Error) => void,
  ) => () => void;
};

export const createApiClient = (baseUrl: string): ApiClient => {
  const httpBaseUrl = baseUrl.replace(/\/$/, "");
  const wsBaseUrl = httpBaseUrl.startsWith("https://")
    ? httpBaseUrl.replace(/^https/, "wss")
    : httpBaseUrl.replace(/^http/, "ws");

  return {
    async createSession(cwd?: string): Promise<SessionRecord> {
      const response = await fetch(`${httpBaseUrl}/sessions`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(cwd ? { cwd } : {}),
      });
      if (!response.ok) {
        throw new Error(`Failed to create session: ${response.status}`);
      }
      return (await response.json()) as SessionRecord;
    },

    async getSession(sessionId: string): Promise<SessionRecord> {
      const response = await fetch(`${httpBaseUrl}/sessions/${sessionId}`);
      if (!response.ok) {
        throw new Error(`Failed to load session: ${response.status}`);
      }
      return (await response.json()) as SessionRecord;
    },

    async sendMessage(sessionId: string, text: string): Promise<SessionRecord> {
      const response = await fetch(`${httpBaseUrl}/sessions/${sessionId}/messages`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!response.ok) {
        throw new Error(`Failed to send message: ${response.status}`);
      }
      return (await response.json()) as SessionRecord;
    },

    async cancelSession(sessionId: string): Promise<SessionRecord> {
      const response = await fetch(`${httpBaseUrl}/sessions/${sessionId}/cancel`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Failed to cancel session: ${response.status}`);
      }
      return (await response.json()) as SessionRecord;
    },

    connectSessionStream(
      sessionId: string,
      onEvent: (event: StreamEvent) => void,
      onError?: (error: Error) => void,
    ): () => void {
      const socket = new WebSocket(`${wsBaseUrl}/sessions/${sessionId}/stream`);

      socket.onmessage = (message) => {
        try {
          onEvent(JSON.parse(String(message.data)) as StreamEvent);
        } catch (error) {
          onError?.(error instanceof Error ? error : new Error(String(error)));
        }
      };

      socket.onerror = () => {
        onError?.(new Error("WebSocket connection failed"));
      };

      return () => socket.close();
    },
  };
};
