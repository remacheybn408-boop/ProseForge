export type SelectionRange = { from: number; to: number };

export function selectedText(content: string, range: SelectionRange): string { return content.slice(range.from, range.to); }
export function buildEditorAction(action: "continue" | "expand" | "shorten" | "rewrite" | "review", content: string, range: SelectionRange, options: Record<string, unknown> = {}) {
  return { action, selection: range, selected_text: selectedText(content, range), options };
}
