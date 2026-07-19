import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

export function PaperPanel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`paper-panel ${className}`}>{children}</section>;
}

export function InkButton({ children, tone = "default", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { tone?: "default" | "vermilion" }) {
  return <button className={`ink-button ink-button-${tone}`} {...props}>{children}</button>;
}

export function BrushDivider() {
  return <div className="brush-divider" aria-hidden="true" />;
}

export function SealBadge({ children, tone = "default", ...props }: { children: ReactNode; tone?: "default" | "success" | "warning" } & HTMLAttributes<HTMLSpanElement>) {
  return <span className={`seal-badge seal-badge-${tone}`} {...props}>{children}</span>;
}

export function EmptyScroll({ children }: { children: ReactNode }) {
  return <div className="empty-scroll">{children}</div>;
}

export function StatusStamp({ children, status = "default" }: { children: ReactNode; status?: "default" | "success" | "error" }) {
  return <span className={`status-stamp status-stamp-${status}`} data-status={status}>{children}</span>;
}
