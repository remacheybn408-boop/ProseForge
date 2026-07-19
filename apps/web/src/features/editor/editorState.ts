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

const SHA256_K = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

const rotr32 = (value: number, bits: number): number => ((value >>> bits) | (value << (32 - bits))) >>> 0;

/**
 * Pure-TS SHA-256 for contexts where WebCrypto is unavailable (plain-http
 * deployments expose no `crypto.subtle`). Kept byte-identical to the WebCrypto
 * result; covered against known vectors in editorState.test.ts.
 */
export function sha256Fallback(bytes: Uint8Array): string {
  const bitLength = bytes.length * 8;
  const paddedLength = (((bytes.length + 8) >> 6) + 1) << 6;
  const padded = new Uint8Array(paddedLength);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(paddedLength - 4, bitLength >>> 0);
  view.setUint32(paddedLength - 8, Math.floor(bitLength / 0x100000000));

  const hash = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  const w = new Array<number>(64);
  for (let block = 0; block < paddedLength; block += 64) {
    for (let index = 0; index < 16; index += 1) w[index] = view.getUint32(block + index * 4);
    for (let index = 16; index < 64; index += 1) {
      const s0 = (rotr32(w[index - 15], 7) ^ rotr32(w[index - 15], 18) ^ (w[index - 15] >>> 3)) >>> 0;
      const s1 = (rotr32(w[index - 2], 17) ^ rotr32(w[index - 2], 19) ^ (w[index - 2] >>> 10)) >>> 0;
      w[index] = (w[index - 16] + s0 + w[index - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, h] = hash;
    for (let index = 0; index < 64; index += 1) {
      const s1 = (rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25)) >>> 0;
      const choice = ((e & f) ^ (~e & g)) >>> 0;
      const temp1 = (h + s1 + choice + SHA256_K[index] + w[index]) >>> 0;
      const s0 = (rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22)) >>> 0;
      const majority = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
      const temp2 = (s0 + majority) >>> 0;
      h = g; g = f; f = e; e = (d + temp1) >>> 0;
      d = c; c = b; b = a; a = (temp1 + temp2) >>> 0;
    }
    hash[0] = (hash[0] + a) >>> 0;
    hash[1] = (hash[1] + b) >>> 0;
    hash[2] = (hash[2] + c) >>> 0;
    hash[3] = (hash[3] + d) >>> 0;
    hash[4] = (hash[4] + e) >>> 0;
    hash[5] = (hash[5] + f) >>> 0;
    hash[6] = (hash[6] + g) >>> 0;
    hash[7] = (hash[7] + h) >>> 0;
  }
  return hash.map(word => word.toString(16).padStart(8, "0")).join("");
}

export async function sha256(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  if (globalThis.crypto?.subtle) {
    const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
  }
  return sha256Fallback(bytes);
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
