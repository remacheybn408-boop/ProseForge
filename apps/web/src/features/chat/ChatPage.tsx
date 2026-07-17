import { useState } from "react";
import { ChatComposer } from "./ChatComposer";
import { MessageList } from "./MessageList";
import type { ChatMessage } from "./chatTypes";

export function ChatPage({ conversationId, branchId, messages = [], onSend = () => undefined, onStop }: { conversationId: string; branchId: string; messages?: ChatMessage[]; onSend?: (text: string) => void; onStop?: () => void }) {
  const [generating, setGenerating] = useState(false);
  return <section className="chat-page-v2"><header><span className="eyebrow">WRITING COMPANION</span><span className="branch-indicator">Branch {branchId}</span></header><MessageList messages={messages} /><ChatComposer conversationId={conversationId} branchId={branchId} generating={generating} onSend={text => { setGenerating(true); onSend(text); }} onStop={() => { setGenerating(false); onStop?.(); }} /></section>;
}
