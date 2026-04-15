import { Box, Text, useApp, useInput } from "ink";
import { useEffect, useRef, useState } from "react";

import type { ApiClient } from "./api";
import { startManagedSession } from "./bootstrap";
import { applyEvent, createInitialState } from "./reducer";
import { formatStatusLabel, renderInputLine, visibleTranscript } from "./view";

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

  const transcript = visibleTranscript(state.transcript, 14);

  return (
    <Box flexDirection="column" paddingX={1} paddingY={0}>
      <Box justifyContent="space-between">
        <Text color="cyan" bold>
          Coder TUI
        </Text>
        <Text dimColor>{state.sessionId ?? "starting..."}</Text>
      </Box>

      <Text color={state.error ? "red" : "white"}>
        {formatStatusLabel(state.status, isBooting, isSending)}
      </Text>
      {state.error ? <Text color="red">Error: {state.error}</Text> : null}

      <Box
        flexDirection="column"
        borderStyle="round"
        borderColor="gray"
        paddingX={1}
        marginTop={1}
        flexGrow={1}
      >
        {transcript.length === 0 ? (
          <Text dimColor>Waiting for the first message...</Text>
        ) : (
          transcript.map((message, index) => (
            <Box key={`${index}-${message.role}`} marginBottom={1} flexDirection="column">
              <Text color={message.role === "user" ? "green" : "magenta"}>
                {message.role}
              </Text>
              <Text>{message.content}</Text>
            </Box>
          ))
        )}
      </Box>

      <Box marginTop={1} borderStyle="round" borderColor="blue" paddingX={1}>
        <Text color="gray">{renderInputLine(draft, true)}</Text>
      </Box>

      <Box marginTop={1} justifyContent="space-between">
        <Text dimColor>Esc / Ctrl-C to quit</Text>
        <Text dimColor>Ctrl-K to cancel</Text>
      </Box>
    </Box>
  );
}
