export type WorkflowRunEvent = { id: string; label: string; status: string; nodeId?: string; at?: string };

export function WorkflowRunTimeline({ events, onFocusNode }: { events: WorkflowRunEvent[]; onFocusNode?: (nodeId: string) => void }) {
  return <section aria-label="Workflow run timeline" style={{ display: "grid", gap: 10 }}><header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><strong style={{ fontFamily: "var(--font-seal)", fontWeight: 500 }}>运行时间线</strong><span style={{ color: "var(--ink-mid)", font: "11px var(--font-mono)" }}>{events.length} 事件</span></header><div className="brush-divider" />
    <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>{events.map(event => <li key={event.id}><button type="button" disabled={!event.nodeId} onClick={() => event.nodeId && onFocusNode?.(event.nodeId)} style={{ width: "100%", display: "flex", justifyContent: "space-between", gap: 12, border: "1px solid var(--ink-faint)", background: "var(--paper-raised)", color: "var(--ink)", padding: "8px 10px", textAlign: "left", cursor: event.nodeId ? "pointer" : "default" }}><span>{event.label}</span><span style={{ color: "var(--ink-mid)", font: "11px var(--font-mono)" }}>{event.at ?? event.status}</span></button></li>)}</ol>
  </section>;
}
