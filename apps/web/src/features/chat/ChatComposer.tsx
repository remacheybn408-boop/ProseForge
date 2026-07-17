import { useEffect, useState } from "react";
import { loadChatDraft, saveChatDraft } from "./chatStore";

export function ChatComposer({ conversationId, branchId, generating = false, onSend, onStop }: { conversationId: string; branchId: string; generating?: boolean; onSend: (text: string) => void; onStop?: () => void }) {
  const [draft, setDraft] = useState(() => loadChatDraft(conversationId, branchId));
  useEffect(() => saveChatDraft(conversationId, branchId, draft), [conversationId, branchId, draft]);
  const submit = () => { if (!draft.trim()) return; onSend(draft.trim()); setDraft(""); };
  return <form className="chat-composer-v2" onSubmit={event => { event.preventDefault(); submit(); }}>
    <textarea aria-label="Message" value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); } }} placeholder="Ask your companion…" />
    <div className="chat-composer-tools"><button type="button" aria-label="Attach file">＋</button><span className="branch-indicator">Branch {branchId}</span>{generating ? <button type="button" onClick={onStop}>Stop</button> : <button className="send-button" type="submit">Send</button>}</div>
  </form>;
}
