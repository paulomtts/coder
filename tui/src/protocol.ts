export type SessionStatus = "idle" | "running" | "cancelled" | "error";

export type SessionMessage = {
  role: "user" | "assistant" | "system" | "tool";
  content: string;
};

export type SessionRecord = {
  session_id: string;
  status: SessionStatus;
  messages: SessionMessage[];
  created_at?: string;
  updated_at?: string;
  cwd?: string | null;
  metadata?: Record<string, unknown>;
};

export type StreamEvent = {
  kind: string;
  session_id: string;
  data: Record<string, unknown>;
  timestamp?: string;
};
