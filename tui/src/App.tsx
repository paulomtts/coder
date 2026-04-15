import { Box, Text, useApp, useInput } from "ink";
import { useEffect, useMemo, useRef, useState } from "react";

import type { ApiClient } from "./api";
import { backspace, clearEditor, createEditorState, deleteForward, insertText, moveCursorLeft, moveCursorRight } from "./editor";
import { startManagedSession } from "./bootstrap";
import { applyEvent, createInitialState } from "./reducer";
import {
  computeViewport,
  createViewportState,
  jumpToLatest,
  jumpToOldest,
  scrollDown,
  scrollUp,
  type ViewportState,
} from "./viewport";
import {
  formatStatusLabel,
  formatViewportLabel,
  renderComposerLine,
  visibleTranscript,
} from "./view";

const TRANSCRIPT_HEIGHT = 14;

export function App() {
  const { exit } = useApp();
  const [state, setState] = useState(createInitialState());
  const [isBooting, setIsBooting] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [viewport, setViewport] = useState<ViewportState>(createViewportState());
  const [editor, setEditor] = useState(createEditorState());
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

  const transcriptViewport = computeViewport({
    transcriptLength: state.transcript.length,
    viewportHeight: TRANSCRIPT_HEIGHT,
    state: viewport,
  });

  const transcript = useMemo(
    () =>
      visibleTranscript(
        state.transcript,
        transcriptViewport.startIndex,
        transcriptViewport.endIndex,
      ),
    [state.transcript, transcriptViewport.endIndex, transcriptViewport.startIndex],
  );

  useEffect(() => {
    if (viewport.followLatest && viewport.scrollOffset === 0) return;
    if (state.transcript.length === 0) return;
    setViewport((current) =>
      current.followLatest ? current : jumpToLatest(),
    );
  }, [state.transcript.length, viewport.followLatest, viewport.scrollOffset]);

  useInput(async (input, key) => {
    if (key.ctrl && input === "c") {
      exit();
      return;
    }

    if (key.escape) {
      setEditor(clearEditor());
      return;
    }

    if (key.pageUp || key.upArrow) {
      setViewport((current) => scrollUp(current, state.transcript.length, TRANSCRIPT_HEIGHT));
      return;
    }

    if (key.pageDown || key.downArrow) {
      setViewport((current) => scrollDown(current, state.transcript.length, TRANSCRIPT_HEIGHT));
      return;
    }

    if (key.pageUp) {
      setViewport(jumpToOldest(state.transcript.length, TRANSCRIPT_HEIGHT));
      return;
    }

    if (key.pageDown) {
      setViewport(jumpToLatest());
      return;
    }

    if (key.return) {
      const sessionId = state.sessionId;
      const api = apiRef.current;
      const message = editor.draft.trim();
      if (!message || !api || !sessionId) return;
      setIsSending(true);
      try {
        await api.sendMessage(sessionId, message);
        setEditor(clearEditor());
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
      return;
    }

    if (key.backspace || key.delete) {
      setEditor((current) => backspace(current));
      return;
    }

    if (key.leftArrow) {
      setEditor((current) => moveCursorLeft(current));
      return;
    }

    if (key.rightArrow) {
      setEditor((current) => moveCursorRight(current));
      return;
    }

    if (input && !key.ctrl && !key.meta) {
      setEditor((current) => insertText(current, input));
    }
  });

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
            <Text dimColor>scroll {transcriptViewport.scrollOffset}</Text>
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
        <Text color="gray">{renderComposerLine(editor.draft, editor.cursor)}</Text>
      </Box>

      <Box marginTop={1} justifyContent="space-between">
        <Text dimColor>/quit to exit</Text>
        <Text dimColor>/up /down /home /end to scroll</Text>
      </Box>
    </Box>
  );
}
