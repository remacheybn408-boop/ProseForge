import type { ChatMessage } from "./chatTypes";
import { MessageCard } from "./MessageCard";

export function MessageList({ messages, onRetry }: { messages: ChatMessage[]; onRetry?: (message: ChatMessage) => void }) {
  return <section className="chat-message-list" aria-live="polite">{messages.length ? messages.map(message => <MessageCard key={message.id} message={message} onRetry={() => onRetry?.(message)} />) : <p className="chat-empty">落笔即是开篇。</p>}</section>;
}
