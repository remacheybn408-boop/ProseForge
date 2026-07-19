import type { EditorActionName, SelectionRange } from "./editorState";

const ACTIONS: EditorActionName[] = ["continue", "expand", "shorten", "rewrite", "change-tone", "review"];

export function SelectionToolbar({ range, onAction }: { range: SelectionRange; onAction: (action: EditorActionName) => void }) {
  return <div className="selection-toolbar" aria-label="Manuscript actions"><span>{range.to - range.from} chars</span>{ACTIONS.map(action => <button key={action} type="button" onClick={() => onAction(action)}>{action}</button>)}</div>;
}
