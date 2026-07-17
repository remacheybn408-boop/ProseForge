import { useState } from "react";
import type { SyntheticEvent } from "react";
import { SelectionToolbar } from "./SelectionToolbar";
import { buildEditorAction, type SelectionRange } from "./editorState";

export function ManuscriptEditor({ initialContent = "", onProposal = () => undefined }: { initialContent?: string; onProposal?: (action: ReturnType<typeof buildEditorAction>) => void }) {
  const [content, setContent] = useState(initialContent);
  const [range, setRange] = useState<SelectionRange>({ from: 0, to: 0 });
  const updateRange = (event: SyntheticEvent<HTMLTextAreaElement>) => { const target = event.currentTarget; setRange({ from: target.selectionStart, to: target.selectionEnd }); };
  return <section className="manuscript-editor"><textarea aria-label="Manuscript" value={content} onChange={event => { setContent(event.target.value); updateRange(event); }} onSelect={updateRange} />{range.to > range.from && <SelectionToolbar range={range} onAction={action => onProposal(buildEditorAction(action as "continue" | "expand" | "shorten" | "rewrite" | "review", content, range))} />}</section>;
}
