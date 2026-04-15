import type { SessionRecord, StreamEvent } from "./protocol";

const baseUrl = process.env.CODER_API_URL ?? "http://127.0.0.1:8000";

export async function createSession(cwd?: string): Promise<SessionRecord> {
  const response = await fetch(`${baseUrl}/sessions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(cwd ? { cwd } : {}),
  });
  if (!response.ok) {
    throw new Error(`Failed to create session: ${response.status}`);
  }
  return (await response.json()) as SessionRecord;
}

export async function getSession(sessionId: string): Promise<SessionRecord> {
  const response = await fetch(`${baseUrl}/sessions/${sessionId}`);
  if (!response.ok) {
    throw new Error(`Failed to load session: ${response.status}`);
  }
  return (await response.json()) as SessionRecord;
}

export async function sendMessage(sessionId: string, text: string): Promise<SessionRecord> {
  const response = await fetch(`${baseUrl}/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) {
    throw new Error(`Failed to send message: ${response.status}`);
  }
  return (await response.json()) as SessionRecord;
}

export async function cancelSession(sessionId: string): Promise<SessionRecord> {
  const response = await fetch(`${baseUrl}/sessions/${sessionId}/cancel`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Failed to cancel session: ${response.status}`);
  }
  return (await response.json()) as SessionRecord;
}

export function connectSessionStream(
  sessionId: string,
  onEvent: (event: StreamEvent) => void,
  onError?: (error: Error) => void,
): () => void {
  const wsBaseUrl = baseUrl.startsWith("https://")
    ? baseUrl.replace(/^https/, "wss")
    : baseUrl.replace(/^http/, "ws");
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
}
