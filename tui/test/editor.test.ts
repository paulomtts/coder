import { describe, expect, test } from "bun:test";

import {
  backspace,
  clearEditor,
  createEditorState,
  deleteForward,
  insertText,
  moveCursorLeft,
  moveCursorRight,
} from "../src/editor";

describe("editor", () => {
  test("inserts text at the cursor", () => {
    const state = insertText(createEditorState(), "hi");
    expect(state).toEqual({ draft: "hi", cursor: 2 });
  });

  test("moves the cursor and deletes text", () => {
    const state = insertText(createEditorState(), "hello");
    const movedLeft = moveCursorLeft(moveCursorLeft(state));
    expect(movedLeft.cursor).toBe(3);
    expect(backspace(movedLeft)).toEqual({ draft: "helo", cursor: 2 });
  });

  test("supports forward delete and clearing", () => {
    const state = { draft: "abc", cursor: 1 };
    expect(deleteForward(state)).toEqual({ draft: "ac", cursor: 1 });
    expect(clearEditor()).toEqual({ draft: "", cursor: 0 });
  });

  test("does not move past the end", () => {
    const state = insertText(createEditorState(), "a");
    expect(moveCursorRight(state).cursor).toBe(1);
  });
});
