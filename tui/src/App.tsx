import { Box, Text, useApp } from "ink";
import { useEffect, useRef, useState } from "react";

import type { ApiClient } from "./api";
import { startManagedSession } from "./bootstrap";
import { parseLineAction } from "./input";
import { applyEvent, createInitialState } from "./reducer";
import {
  computeViewport,
  createViewportState,
  jumpToLatest,
  jumpToOldest,
  scrollDown,
  scrollUp,
} from "./viewport";
import {
  formatStatusLabel,
  formatViewportLabel,
  visibleTranscript,
} from "./view";

export function App() {
  const { exit } = useApp();
  const [state, setState] = useState(createInitialState());
  const [isBooting, setIsBooting] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [viewport, setViewport] = useState(createViewportState());
  const apiRef = useRef<ApiClient | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const transcriptLengthRef = useRef(0);
  const viewportRef = useRef(viewport);

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

  useEffect(() => {
    sessionIdRef.current = state.sessionId;
    transcriptLengthRef.current = state.transcript.length;
    viewportRef.current = viewport;
  }, [state.sessionId, state.transcript.length, viewport]);

  const transcriptViewport = computeViewport({
    transcriptLength: state.transcript.length,
    viewportHeight: 14,
    state: viewport,
  });
  const transcript = visibleTranscript(
    state.transcript,
    transcriptViewport.startIndex,
    transcriptViewport.endIndex,
  );

  useEffect(() => {
    let cancelled = false;
    const decoder = new TextDecoder();
    const reader = Bun.stdin.stream().getReader();
    let buffer = "";

    (async () => {
      while (!cancelled) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let newlineIndex = buffer.indexOf("\n");
        while (newlineIndex !== -1) {
          const rawLine = buffer.slice(0, newlineIndex).replace(/\r$/, "");
          buffer = buffer.slice(newlineIndex + 1);
          const action = parseLineAction(rawLine);
          const sessionId = sessionIdRef.current;
          const transcriptLength = transcriptLengthRef.current;

          if (action.type === "quit") {
            exit();
            return;
          }

          if (action.type === "cancel") {
            if (sessionId) {
              try {
                await apiRef.current?.cancelSession(sessionId);
              } catch (error) {
                setState((current) =>
                  applyEvent(current, {
                    kind: "session.error",
                    session_id: sessionId,
                    data: { error: error instanceof Error ? error.message : String(error) },
                  }),
                );
              }
            }
            newlineIndex = buffer.indexOf("\n");
            continue;
          }

          if (action.type === "scroll-up") {
            setViewport((current) => scrollUp(current, transcriptLength, 14));
          } else if (action.type === "scroll-down") {
            setViewport((current) => scrollDown(current, transcriptLength, 14));
          } else if (action.type === "scroll-home") {
            setViewport(jumpToOldest(transcriptLength, 14));
          } else if (action.type === "scroll-end") {
            setViewport(jumpToLatest());
          } else if (action.type === "message") {
            const text = action.text.trim();
            if (text && apiRef.current && sessionId) {
              setIsSending(true);
              try {
                await apiRef.current.sendMessage(sessionId, text);
              } catch (error) {
                setState((current) =>
                  applyEvent(current, {
                    kind: "session.error",
                    session_id: sessionId,
                    data: { error: error instanceof Error ? error.message : String(error) },
                  }),
                );
              } finally {
                setIsSending(false);
              }
            }
          }

          newlineIndex = buffer.indexOf("\n");
        }
      }
    })();

    return () => {
      cancelled = true;
      reader.cancel().catch(() => undefined);
    };
  }, [exit]);

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
        {" · "}
        {formatViewportLabel(transcriptViewport.followLatest)}
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
        <Box justifyContent="space-between">
          <Text dimColor>
            {state.transcript.length === 0
              ? "Waiting for the first message..."
              : `Messages ${transcriptViewport.startIndex + 1}-${transcriptViewport.endIndex} of ${state.transcript.length}`}
          </Text>
          {!transcriptViewport.followLatest ? (
            <Text dimColor>
              scroll {transcriptViewport.scrollOffset}
            </Text>
          ) : null}
        </Box>
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
        <Text color="gray">&gt; Type a message and press Enter</Text>
      </Box>

      <Box marginTop={1} justifyContent="space-between">
        <Text dimColor>/quit to exit</Text>
        <Text dimColor>/up /down /home /end to scroll</Text>
      </Box>
    </Box>
  );
}
