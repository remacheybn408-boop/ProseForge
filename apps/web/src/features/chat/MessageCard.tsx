import DOMPurify from "dompurify";
import { useRef, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import { StatusStamp } from "../../components/ink/Ink";
import type { ChatMessage } from "./chatTypes";

function CodeBlock({ children }: { children?: ReactNode }) {
  const block = useRef<HTMLPreElement>(null);
  const copy = () => {
    const text = block.current?.textContent ?? "";
    if (typeof navigator !== "undefined" && navigator.clipboard) void navigator.clipboard.writeText(text);
  };
  return <div className="code-block"><button type="button" className="code-copy" onClick={copy}>Copy</button><pre ref={block}>{children}</pre></div>;
}

export function MessageCard({ message, onRetry }: { message: ChatMessage; onRetry?: () => void }) {
  const streaming = message.status === "streaming";
  const failed = message.status === "failed" || message.status === "cancelled";
  return <article className={`chat-message-card chat-message-${message.role}${streaming ? " streaming" : ""}${failed ? " failed" : ""}`} aria-label={`${message.role} message`}>
    {message.branchCount !== undefined && <span className="branch-switcher">‹ {message.branchIndex ?? 1}/{message.branchCount} ›</span>}
    <div className="chat-message-body">
      {message.role === "assistant" && message.content ? <ReactMarkdown components={{ pre: CodeBlock }}>{DOMPurify.sanitize(message.content)}</ReactMarkdown> : null}
      {message.role !== "assistant" ? message.content : null}
      {!message.content && message.status === "pending" ? "Thinking…" : null}
      {streaming && <span className="streaming-cursor" aria-hidden="true" />}
    </div>
    {failed && <div className="message-failed"><StatusStamp>止</StatusStamp>{onRetry && <button type="button" onClick={onRetry}>Retry</button>}</div>}
  </article>;
}
