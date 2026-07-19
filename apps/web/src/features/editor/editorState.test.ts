import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import {
  beginOptimisticSave,
  buildEditorAction,
  createLocalEditorDraft,
  defaultActionParams,
  proseMirrorRangeToTextRange,
  resolveOptimisticSave,
  restoreLocalEditorDraft,
  sha256,
  sha256Fallback,
  toSelectionActionRequest,
  updateLocalEditorDraft,
} from "./editorState";

describe("editor state", () => {
  it("uses Tiptap document positions and serializes the selection-actions request", async () => {
    const editor = new Editor({ extensions: [StarterKit], content: "Mira enters." });
    editor.commands.setTextSelection({ from: 1, to: 5 });
    const proseMirrorRange = { from: editor.state.selection.from, to: editor.state.selection.to };
    const textRange = proseMirrorRangeToTextRange(editor.state.doc, proseMirrorRange);
    const action = await buildEditorAction("change-tone", editor.getText({ blockSeparator: "\n" }), textRange, "version-1", { register: "formal" }, proseMirrorRange);
    expect(action).toMatchObject({ from: 0, to: 4, content: "Mira enters.", selectedText: "Mira", baseVersionId: "version-1", proseMirrorRange: { from: 1, to: 5 }, params: { register: "formal", sensory: [] } });
    expect(action.selectedTextHash).toMatch(/^[a-f0-9]{64}$/);
    expect(toSelectionActionRequest(action)).toEqual({ action: "change-tone", from: 0, to: 4, selected_text_hash: action.selectedTextHash, base_version_id: "version-1", params: action.params });
    editor.destroy();
  });

  it("maps a cross-paragraph ProseMirror range to the exact API text offsets", () => {
    const editor = new Editor({
      extensions: [StarterKit],
      content: {
        type: "doc",
        content: [
          { type: "paragraph", content: [{ type: "text", text: "one" }] },
          { type: "paragraph", content: [{ type: "text", text: "two" }] },
        ],
      },
    });
    const proseMirrorRange = { from: 1, to: 9 };
    const textRange = proseMirrorRangeToTextRange(editor.state.doc, proseMirrorRange);
    expect(editor.getText({ blockSeparator: "\n" })).toBe("one\ntwo");
    expect(textRange).toEqual({ from: 0, to: 7 });
    editor.destroy();
  });

  it("uses the backend parameter names and ratio defaults", () => {
    expect(defaultActionParams("continue")).toEqual({ candidates: 3 });
    expect(defaultActionParams("expand")).toEqual({ ratio: 2 });
    expect(defaultActionParams("shorten")).toEqual({ ratio: 0.7 });
  });

  it("restores only dirty local drafts and can roll an optimistic conflict back", () => {
    const loaded = createLocalEditorDraft("server");
    const dirty = updateLocalEditorDraft(loaded, "local edit");
    expect(restoreLocalEditorDraft("new server", dirty).content).toBe("local edit");
    const saving = beginOptimisticSave(dirty);
    expect(resolveOptimisticSave(saving, false, "server")).toMatchObject({ content: "local edit", savedContent: "server", dirty: true, pendingSave: false });
  });
});

describe("sha256", () => {
  it("fallback matches published vectors", () => {
    expect(sha256Fallback(new TextEncoder().encode(""))).toBe("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    expect(sha256Fallback(new TextEncoder().encode("abc"))).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });

  it("sha256 resolves identically with or without WebCrypto", async () => {
    const text = "Mira unfolded the brass map.";
    await expect(sha256(text)).resolves.toBe(sha256Fallback(new TextEncoder().encode(text)));
    const action = await buildEditorAction("review", text, { from: 0, to: 4 });
    expect(action.selectedTextHash).toMatch(/^[a-f0-9]{64}$/);
  });
});
