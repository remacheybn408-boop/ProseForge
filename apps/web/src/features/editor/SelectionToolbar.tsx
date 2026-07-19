import type { EditorActionName, SelectionRange } from "./editorState";

const ACTIONS: EditorActionName[] = ["continue", "expand", "shorten", "rewrite", "change-tone", "review"];

export function SelectionToolbar({ range, onAction }: { range: SelectionRange; onAction: (action: EditorActionName) => void }) {
  // Prevent the toolbar click from blurring the editor: blur collapses the
  // selection, which unmounts this toolbar mid-click and the action is lost.
  return <div className="selection-toolbar" aria-label="Manuscript actions" onMouseDown={event => event.preventDefault()}><span>{range.to - range.from} chars</span>{ACTIONS.map(action => <button key={action} type="button" onClick={() => onAction(action)}>{action}</button>)}</div>;
}
