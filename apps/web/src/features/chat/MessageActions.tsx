import { useState } from "react";
import type { ChatMessage } from "./chatTypes";

export function MessageActions({ message, candidateIndex, candidateCount, onSwitchCandidate, onEdit, onRegenerate }: {
  message: ChatMessage;
  candidateIndex?: number;
  candidateCount?: number;
  onSwitchCandidate?: (direction: 1 | -1) => void;
  onEdit?: (content: string) => void;
  onRegenerate?: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);

  if (editing) {
    const save = () => {
      const content = draft.trim();
      if (!content || !onEdit) return;
      onEdit(content);
      setEditing(false);
    };
    return <div className="message-actions editing">
      <textarea aria-label="Edit message" rows={3} value={draft} onChange={event => setDraft(event.target.value)} />
      <div className="message-actions-row">
        <button type="button" onClick={save}>Save edit</button>
        <button type="button" onClick={() => { setDraft(message.content); setEditing(false); }}>Cancel</button>
      </div>
    </div>;
  }

  const showSwitcher = Boolean(onSwitchCandidate && candidateIndex !== undefined && candidateCount !== undefined && candidateCount > 1);
  if (!showSwitcher && !onEdit && !onRegenerate) return null;

  return <div className="message-actions">
    {showSwitcher && <span className="candidate-switcher">
      <button type="button" aria-label="Previous candidate" onClick={() => onSwitchCandidate?.(-1)}>‹</button>
      <span className="candidate-counter">{candidateIndex}/{candidateCount}</span>
      <button type="button" aria-label="Next candidate" onClick={() => onSwitchCandidate?.(1)}>›</button>
    </span>}
    {onEdit && <button type="button" onClick={() => { setDraft(message.content); setEditing(true); }}>Edit</button>}
    {onRegenerate && <button type="button" onClick={onRegenerate}>Regenerate</button>}
  </div>;
}
