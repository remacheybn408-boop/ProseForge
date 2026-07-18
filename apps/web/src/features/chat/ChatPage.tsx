import { PaperPanel } from "../../components/ink/Ink";
import { WorkspaceSplit } from "../../components/layout/WorkspaceSplit";
import { ChatComposer } from "./ChatComposer";
import { MessageList } from "./MessageList";
import type { ChatMessage, SendOptions } from "./chatTypes";

export function ChatPage({ conversationId, branchId, messages = [], error, notice, onSend = () => undefined, onStop, onRetry, onFork, onReload }: {
  conversationId: string;
  branchId: string;
  messages?: ChatMessage[];
  error?: string;
  notice?: string;
  onSend?: (text: string, options?: SendOptions) => void;
  onStop?: () => void;
  onRetry?: (message: ChatMessage) => void;
  onFork?: () => void;
  onReload?: () => void;
}) {
  const generating = messages.some(message => message.status === "streaming" || message.status === "pending");
  return <WorkspaceSplit inspector={<PaperPanel><h3>Conversation</h3><p>Branch {branchId}</p><p>{messages.length} messages</p></PaperPanel>}>
    <section className="chat-page-v2">
      <header>
        <span className="eyebrow">WRITING COMPANION</span>
        <span className="branch-indicator">Branch {branchId}</span>
        {onFork && <button type="button" onClick={onFork} disabled={!messages.some(message => message.role === "assistant")}>Fork branch</button>}
      </header>
      {notice && <p className="chat-notice" aria-live="polite">{notice}</p>}
      {error ? <div className="chat-error-card" role="alert"><p>We could not load this conversation.</p><code>{error}</code>{onReload && <button type="button" onClick={onReload}>Retry</button>}</div> : <MessageList messages={messages} onRetry={onRetry} />}
      <ChatComposer conversationId={conversationId} branchId={branchId} generating={generating} onSend={onSend} onStop={onStop} />
    </section>
  </WorkspaceSplit>;
}
