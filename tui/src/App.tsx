import { Box, Text, useApp, useInput } from "ink";
import { useEffect, useRef, useState } from "react";

import { applyEvent, createInitialState } from "./reducer";
import { startManagedSession } from "./bootstrap";
import type { ApiClient } from "./api";

export function App() {
  const { exit } = useApp();
  const [state, setState] = useState(createInitialState());
  const [draft, setDraft] = useState("");
  const [isBooting, setIsBooting] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const apiRef = useRef<ApiClient | null>(null);

  useEffect(() => {
    let cancelled = false;
    let shutdown = async () => {};

    (async () => {
      try {
        const handle = await startManagedSession({
          onEvent: (event) => {
            setState((current) => applyEvent(current, event));
          },
        });

        if (cancelled) {
          await handle.shutdown();
          return;
        }

        apiRef.current = handle.api;
        shutdown = handle.shutdown;
        setState((current) =>
          applyEvent(current, {
            kind: "session.created",
            session_id: handle.session.session_id,
            data: { session_id: handle.session.session_id },
          }),
        );
      } catch (error) {
        if (!cancelled) {
          setState((current) =>
            applyEvent(current, {
              kind: "session.error",
              session_id: "",
              data: { error: error instanceof Error ? error.message : String(error) },
            }),
          );
        }
      } finally {
        if (!cancelled) {
          setIsBooting(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      void shutdown();
    };
  }, []);

  useInput(async (input, key) => {
    if (key.escape || (key.ctrl && input === "c")) {
      exit();
      return;
    }

    if (!state.sessionId) return;

    if (key.ctrl && input === "k") {
      try {
        await apiRef.current?.cancelSession(state.sessionId);
      } catch (error) {
        setState((current) =>
          applyEvent(current, {
            kind: "session.error",
            session_id: state.sessionId!,
            data: { error: error instanceof Error ? error.message : String(error) },
          }),
        );
      }
      return;
    }

    if (key.return) {
      const text = draft.trim();
      if (!text || !apiRef.current) return;
      setDraft("");
      setIsSending(true);
      try {
        await apiRef.current.sendMessage(state.sessionId, text);
      } catch (error) {
        setState((current) =>
          applyEvent(current, {
            kind: "session.error",
            session_id: state.sessionId!,
            data: { error: error instanceof Error ? error.message : String(error) },
          }),
        );
      } finally {
        setIsSending(false);
      }
      return;
    }

    if (key.backspace || key.delete) {
      setDraft((current) => current.slice(0, -1));
      return;
    }

    if (input && !key.ctrl && !key.meta) {
      setDraft((current) => current + input);
    }
  });

  return (
    <Box flexDirection="column">
      <Text color="cyan">Coder TUI</Text>
      <Text>Session: {state.sessionId ?? "starting..."}</Text>
      <Text>
        Status: {state.status}
        {isBooting ? " (booting)" : ""}
        {isSending ? " (sending)" : ""}
      </Text>
      {state.error ? <Text color="red">Error: {state.error}</Text> : null}
      <Box flexDirection="column" marginTop={1}>
        {state.transcript.map((message, index) => (
          <Text key={`${index}-${message.role}`}>
            <Text color={message.role === "user" ? "green" : "magenta"}>
              {message.role}: 
            </Text>
            {message.content}
          </Text>
        ))}
      </Box>
      <Box marginTop={1}>
        <Text color="gray">{draft || "Type a message and press Enter"}</Text>
      </Box>
      <Box marginTop={1}>
        <Text dimColor>Press Esc or Ctrl-C to quit</Text>
      </Box>
      <Box marginTop={1}>
        <Text dimColor>Cancel the active run with Ctrl-K</Text>
      </Box>
    </Box>
  );
}
