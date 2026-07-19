export type EditorActionName = "continue" | "expand" | "shorten" | "rewrite" | "change-tone" | "review";

/** A half-open range in the canonical plain-text chapter content. */
export type SelectionRange = { from: number; to: number };

/** The original editor coordinates; ProseMirror positions are not text offsets. */
export type ProseMirrorRange = { from: number; to: number };

type TextBetweenDocument = {
  content: { size: number };
  textBetween: (from: number, to: number, blockSeparator?: string) => string;
};

export type EditorAction = {
  action: EditorActionName;
  from: number;
  to: number;
  content: string;
  selectedText: string;
  selectedTextHash: string;
  baseVersionId: string | null;
  params: Record<string, unknown>;
  /** Kept for UI anchoring; never send this directly to the text-offset API. */
  proseMirrorRange: ProseMirrorRange | null;
};

export type SelectionActionRequest = {
  action: EditorActionName;
  from: number;
  to: number;
  selected_text_hash: string;
  base_version_id: string | null;
  params: Record<string, unknown>;
};

export type LocalEditorDraft = {
  content: string;
  savedContent: string;
  dirty: boolean;
  pendingSave: boolean;
};

const DEFAULT_PARAMS: Record<EditorActionName, Record<string, unknown>> = {
  continue: { candidates: 3 },
  expand: { ratio: 2 },
  shorten: { ratio: 0.7 },
  rewrite: { instruction: "" },
  "change-tone": { register: "neutral", sensory: [] },
  review: {},
};

export function selectedText(content: string, range: SelectionRange): string {
  return content.slice(range.from, range.to);
}

/**
 * ProseMirror positions include structural nodes (for example a paragraph's
 * opening token), while the API validates offsets against plain chapter text.
 * ``textBetween`` applies the same block separator used to derive editor text,
 * so this also remains correct when a selection crosses paragraphs.
 */
export function proseMirrorRangeToTextRange(document: TextBetweenDocument, range: ProseMirrorRange, blockSeparator = "\n"): SelectionRange {
  const prefix = document.textBetween(0, range.from, blockSeparator);
  const selected = document.textBetween(range.from, range.to, blockSeparator);
  return { from: prefix.length, to: prefix.length + selected.length };
}

export function defaultActionParams(action: EditorActionName): Record<string, unknown> {
  return { ...DEFAULT_PARAMS[action] };
}

export async function sha256(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}

export async function buildEditorAction(
  action: EditorActionName,
  content: string,
  range: SelectionRange,
  baseVersionId: string | null = null,
  params: Record<string, unknown> = {},
  proseMirrorRange: ProseMirrorRange | null = null,
): Promise<EditorAction> {
  const text = selectedText(content, range);
  return {
    action,
    from: range.from,
    to: range.to,
    content,
    selectedText: text,
    selectedTextHash: await sha256(text),
    baseVersionId,
    params: { ...defaultActionParams(action), ...params },
    proseMirrorRange,
  };
}

/** Convert the editor-only payload to the V2 selection-actions HTTP contract. */
export function toSelectionActionRequest(action: EditorAction): SelectionActionRequest {
  return {
    action: action.action,
    from: action.from,
    to: action.to,
    selected_text_hash: action.selectedTextHash,
    base_version_id: action.baseVersionId,
    params: action.params,
  };
}

export function createLocalEditorDraft(content: string, savedContent = content): LocalEditorDraft {
  return { content, savedContent, dirty: content !== savedContent, pendingSave: false };
}

/** Keep a local dirty draft on refresh; otherwise trust the server version. */
export function restoreLocalEditorDraft(serverContent: string, draft: LocalEditorDraft | null | undefined): LocalEditorDraft {
  if (draft?.dirty) return { ...draft, pendingSave: false };
  return createLocalEditorDraft(serverContent);
}

export function updateLocalEditorDraft(draft: LocalEditorDraft, content: string): LocalEditorDraft {
  return { ...draft, content, dirty: content !== draft.savedContent };
}

/** Mark a save as in-flight without losing the value needed to roll back a 409. */
export function beginOptimisticSave(draft: LocalEditorDraft): LocalEditorDraft {
  return { ...draft, savedContent: draft.content, dirty: false, pendingSave: true };
}

export function resolveOptimisticSave(draft: LocalEditorDraft, accepted: boolean, previousSavedContent: string): LocalEditorDraft {
  if (accepted) return { ...draft, pendingSave: false };
  return { ...draft, savedContent: previousSavedContent, dirty: draft.content !== previousSavedContent, pendingSave: false };
}
