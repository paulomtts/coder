export type EditorState = {
  draft: string;
  cursor: number;
};

export const createEditorState = (): EditorState => ({
  draft: "",
  cursor: 0,
});

export function insertText(state: EditorState, text: string): EditorState {
  const nextDraft = state.draft.slice(0, state.cursor) + text + state.draft.slice(state.cursor);
  return {
    draft: nextDraft,
    cursor: state.cursor + text.length,
  };
}

export function moveCursorLeft(state: EditorState): EditorState {
  return {
    ...state,
    cursor: Math.max(0, state.cursor - 1),
  };
}

export function moveCursorRight(state: EditorState): EditorState {
  return {
    ...state,
    cursor: Math.min(state.draft.length, state.cursor + 1),
  };
}

export function backspace(state: EditorState): EditorState {
  if (state.cursor === 0) return state;
  return {
    draft: state.draft.slice(0, state.cursor - 1) + state.draft.slice(state.cursor),
    cursor: state.cursor - 1,
  };
}

export function deleteForward(state: EditorState): EditorState {
  if (state.cursor >= state.draft.length) return state;
  return {
    draft: state.draft.slice(0, state.cursor) + state.draft.slice(state.cursor + 1),
    cursor: state.cursor,
  };
}

export function clearEditor(): EditorState {
  return createEditorState();
}
