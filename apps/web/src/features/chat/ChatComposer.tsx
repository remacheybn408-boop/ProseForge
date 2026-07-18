import { useEffect, useRef, useState } from "react";
import { loadDraft, saveDraft } from "../../lib/drafts";
import { ModelPicker } from "../models/ModelPicker";
import { ReasoningPicker } from "../models/ReasoningPicker";
import { modelKey, supportedReasoning, useModelCatalog, type ReasoningLevel } from "../models/modelCapabilities";
import { useChatStore } from "./chatStore";
import type { SendOptions } from "./chatTypes";

const MAX_ATTACHMENT_BYTES = 2 * 1024 * 1024;

export function ChatComposer({ conversationId, branchId, generating = false, onSend, onStop }: {
  conversationId: string;
  branchId: string;
  generating?: boolean;
  onSend: (text: string, options?: SendOptions) => void;
  onStop?: () => void;
}) {
  const [draft, setDraft] = useState("");
  const [restored, setRestored] = useState(false);
  const [attachments, setAttachments] = useState<{ name: string; size: number }[]>([]);
  const [notice, setNotice] = useState("");
  const [selectedKey, setSelectedKey] = useState("");
  const [reasoning, setReasoning] = useState<ReasoningLevel>("auto");
  const fileInput = useRef<HTMLInputElement>(null);
  const modelsQuery = useModelCatalog();
  const models = modelsQuery.data ?? [];
  const selected = models.find(model => modelKey(model) === selectedKey);
  const paletteOpen = useChatStore(state => state.commandPaletteOpen);
  const setPaletteOpen = useChatStore(state => state.setCommandPaletteOpen);

  useEffect(() => {
    let active = true;
    setRestored(false);
    setDraft("");
    loadDraft({ conversationId, branchId, draftType: "chat" }).then(value => { if (!active) return; if (value) setDraft(value); setRestored(true); }).catch(() => { if (active) setRestored(true); });
    return () => { active = false; };
  }, [conversationId, branchId]);

  useEffect(() => { if (restored) void saveDraft({ conversationId, branchId, draftType: "chat" }, draft).catch(() => undefined); }, [restored, conversationId, branchId, draft]);

  const submit = () => {
    const text = draft.trim();
    if (!text) return;
    onSend(text, { provider: selected?.provider, model: selected?.model_id, reasoning });
    setDraft("");
    setAttachments([]);
  };

  const pickFile = (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    if (file.size > MAX_ATTACHMENT_BYTES) {
      setNotice(`${file.name} exceeds the 2MB limit.`);
      return;
    }
    setNotice("");
    setAttachments(current => [...current, { name: file.name, size: file.size }]);
  };

  return <form className="chat-composer-v2" onSubmit={event => { event.preventDefault(); submit(); }}>
    <input ref={fileInput} className="attachment-input" type="file" accept=".txt,.md,.docx" aria-label="Attachment file" onChange={event => { pickFile(event.target.files); event.target.value = ""; }} />
    {attachments.length > 0 && <ul className="attachment-list">{attachments.map(file => <li className="attachment-chip" key={file.name}>{file.name} · {Math.round(file.size / 1024)}KB<button type="button" aria-label={`Remove ${file.name}`} onClick={() => setAttachments(current => current.filter(item => item.name !== file.name))}>×</button></li>)}</ul>}
    <textarea aria-label="Message" value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => {
      if (event.key === "k" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); setPaletteOpen(!paletteOpen); return; }
      if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); }
    }} placeholder="Ask your companion…" />
    <p className="composer-notice" aria-live="polite">{notice}</p>
    <div className="chat-composer-tools">
      <button type="button" aria-label="Attach file" onClick={() => fileInput.current?.click()}>＋</button>
      <ModelPicker models={models} value={selectedKey} onChange={model => setSelectedKey(modelKey(model))} />
      <ReasoningPicker value={reasoning} supported={selected ? supportedReasoning(selected) : ["auto"]} onChange={setReasoning} />
      <span className="branch-indicator">Branch {branchId}</span>
      <span className="composer-status" aria-live="polite">{generating ? "Generating…" : ""}</span>
      {generating ? <button type="button" className="stop-stamp" aria-label="Stop generation" onClick={onStop}>止</button> : <button className="send-button" type="submit">Send</button>}
    </div>
    {paletteOpen && <div className="command-palette" role="dialog" aria-modal="true" aria-label="Command palette" onKeyDown={event => { if (event.key === "Escape") setPaletteOpen(false); }}>
      <div className="command-palette-panel">
        <button type="button" onClick={() => { submit(); setPaletteOpen(false); }}>Send message</button>
        <button type="button" onClick={() => { setDraft(""); setPaletteOpen(false); }}>Clear draft</button>
        <button type="button" onClick={() => setPaletteOpen(false)}>Close</button>
      </div>
    </div>}
  </form>;
}
