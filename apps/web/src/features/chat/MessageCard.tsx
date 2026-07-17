import type { ChatMessage } from "./chatTypes";

export function MessageCard({ message, onRetry }: { message: ChatMessage; onRetry?: () => void }) {
  const streaming = message.status === "streaming";
  return <article className={`chat-message-card chat-message-${message.role}`} aria-label={`${message.role} message`}>
    <div className="chat-message-body">{message.content || (message.status === "pending" ? "Thinking…" : "")}{streaming && <span className="streaming-cursor" aria-hidden="true" />}</div>
    {message.branchCount !== undefined && <span className="branch-counter">↳ {message.branchCount} branches</span>}
    {message.status === "failed" && <button type="button" onClick={onRetry}>Retry</button>}
  </article>;
}
