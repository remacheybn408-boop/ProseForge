import { Fragment, type ReactNode } from "react";
import { BrushDivider, EmptyScroll } from "../../components/ink/Ink";
import { MessageCard } from "./MessageCard";
import type { ChatMessage } from "./chatTypes";

export function MessageList({ messages, onRetry, renderActions }: { messages: ChatMessage[]; onRetry?: (message: ChatMessage) => void; renderActions?: (message: ChatMessage) => ReactNode }) {
  if (messages.length === 0) {
    return <section className="chat-message-list" aria-live="polite"><EmptyScroll><p className="empty-scroll-title">落笔即是开篇。</p><p className="empty-scroll-hint">Try an opening prompt: “Draft the first scene where Mira reaches the flooded archive.”</p></EmptyScroll></section>;
  }
  return <section className="chat-message-list" aria-live="polite">
    {messages.map((message, index) => <Fragment key={message.id}>{index > 0 && message.role === "user" && <BrushDivider />}<MessageCard message={message} onRetry={onRetry ? () => onRetry(message) : undefined} actions={renderActions?.(message)} /></Fragment>)}
  </section>;
}
