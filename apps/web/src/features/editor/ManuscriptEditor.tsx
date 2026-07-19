import { Component, useEffect, useRef, useState } from "react";
import type { ErrorInfo, ReactNode, SyntheticEvent } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { SelectionToolbar } from "./SelectionToolbar";
import {
  buildEditorAction,
  createLocalEditorDraft,
  restoreLocalEditorDraft,
  updateLocalEditorDraft,
  type EditorAction,
  type EditorActionName,
  type LocalEditorDraft,
  proseMirrorRangeToTextRange,
  type ProseMirrorRange,
  type SelectionRange,
} from "./editorState";

type ManuscriptEditorProps = {
  /** Controlled text content. Omit to let the editor own its value. */
  content?: string;
  initialContent?: string;
  baseVersionId?: string | null;
  initialDraft?: LocalEditorDraft | null;
  forcePlain?: boolean;
  onContentChange?: (content: string) => void;
  onDraftChange?: (draft: LocalEditorDraft) => void;
  onSave?: (content: string) => void | Promise<void>;
  onAction?: (action: EditorAction) => void | Promise<void>;
  /** Compatibility alias until all callers move to onAction. */
  onProposal?: (action: EditorAction) => void | Promise<void>;
};

type FailureBoundaryProps = { onFailure: (error: Error) => void; children: ReactNode };
type FailureBoundaryState = { failed: boolean };

class EditorFailureBoundary extends Component<FailureBoundaryProps, FailureBoundaryState> {
  state: FailureBoundaryState = { failed: false };

  static getDerivedStateFromError(): FailureBoundaryState { return { failed: true }; }

  componentDidCatch(error: Error, _info: ErrorInfo) { this.props.onFailure(error); }

  render() { return this.state.failed ? null : this.props.children; }
}

function isPlainEditorRequested(): boolean {
  return typeof window !== "undefined" && new URLSearchParams(window.location.search).get("editor") === "plain";
}

type EditorSelection = { textRange: SelectionRange; proseMirrorRange: ProseMirrorRange | null };

function PlainTextEditor({ content, onContentChange, onSelectionChange }: { content: string; onContentChange: (content: string) => void; onSelectionChange: (selection: EditorSelection) => void }) {
  const updateRange = (event: SyntheticEvent<HTMLTextAreaElement>) => {
    const target = event.currentTarget;
    onSelectionChange({ textRange: { from: target.selectionStart, to: target.selectionEnd }, proseMirrorRange: null });
  };
  return <textarea aria-label="Manuscript" value={content} onChange={event => { onContentChange(event.target.value); updateRange(event); }} onSelect={updateRange} />;
}

function TiptapEditor({ content, onContentChange, onSelectionChange }: { content: string; onContentChange: (content: string) => void; onSelectionChange: (selection: EditorSelection) => void }) {
  const onContentChangeRef = useRef(onContentChange);
  const onSelectionChangeRef = useRef(onSelectionChange);
  onContentChangeRef.current = onContentChange;
  onSelectionChangeRef.current = onSelectionChange;
  const editor = useEditor({
    extensions: [StarterKit],
    content,
    immediatelyRender: false,
    editorProps: { attributes: { "aria-label": "Manuscript", "data-testid": "tiptap-manuscript" } },
    onUpdate: ({ editor: currentEditor }) => onContentChangeRef.current(currentEditor.getText({ blockSeparator: "\n" })),
    onSelectionUpdate: ({ editor: currentEditor }) => {
      const proseMirrorRange = { from: currentEditor.state.selection.from, to: currentEditor.state.selection.to };
      onSelectionChangeRef.current({ textRange: proseMirrorRangeToTextRange(currentEditor.state.doc, proseMirrorRange), proseMirrorRange });
    },
  });

  useEffect(() => {
    if (editor && editor.getText({ blockSeparator: "\n" }) !== content) editor.commands.setContent(content, { emitUpdate: false });
  }, [content, editor]);

  return <EditorContent editor={editor} />;
}

export function ManuscriptEditor({ content: controlledContent, initialContent = "", baseVersionId = null, initialDraft = null, forcePlain = false, onContentChange, onDraftChange, onSave, onAction, onProposal }: ManuscriptEditorProps) {
  const [draft, setDraft] = useState(() => restoreLocalEditorDraft(controlledContent ?? initialContent, initialDraft));
  const [selection, setSelection] = useState<EditorSelection>({ textRange: { from: 0, to: 0 }, proseMirrorRange: null });
  const [plainFallback, setPlainFallback] = useState(() => forcePlain || isPlainEditorRequested());
  const content = controlledContent ?? draft.content;

  useEffect(() => {
    if (controlledContent !== undefined) setDraft(current => current.content === controlledContent ? current : createLocalEditorDraft(controlledContent, current.savedContent));
  }, [controlledContent]);

  const changeContent = (nextContent: string) => {
    const nextDraft = updateLocalEditorDraft(draft, nextContent);
    if (controlledContent === undefined) setDraft(nextDraft);
    onContentChange?.(nextContent);
    onDraftChange?.(nextDraft);
  };
  const runAction = async (action: EditorActionName) => {
    const result = await buildEditorAction(action, content, selection.textRange, baseVersionId, {}, selection.proseMirrorRange);
    await onAction?.(result);
    await onProposal?.(result);
  };
  const activateFallback = (error: Error) => {
    console.warn("Tiptap initialization failed; using the plain text editor.", error);
    setPlainFallback(true);
  };

  return <section className="manuscript-editor">
    {plainFallback ? <PlainTextEditor content={content} onContentChange={changeContent} onSelectionChange={setSelection} /> : <EditorFailureBoundary onFailure={activateFallback}><TiptapEditor content={content} onContentChange={changeContent} onSelectionChange={setSelection} /></EditorFailureBoundary>}
    {selection.textRange.to > selection.textRange.from ? <SelectionToolbar range={selection.textRange} onAction={action => { void runAction(action); }} /> : null}
    {onSave ? <button type="button" onClick={() => { void onSave(content); }} disabled={!draft.dirty}>Save version</button> : null}
  </section>;
}
