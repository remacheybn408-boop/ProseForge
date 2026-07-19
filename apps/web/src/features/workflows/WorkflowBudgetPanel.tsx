export function WorkflowBudgetPanel({ used, limit }: { used: number; limit: number }) {
  const ratio = limit > 0 ? Math.min(1, used / limit) : 0;
  const percent = Math.round(ratio * 100);
  return <section aria-label="Workflow budget" style={{ display: "flex", gap: 14, alignItems: "center", padding: "12px 0", color: "var(--ink)" }}>
    <div role="progressbar" aria-label="预算使用量" aria-valuenow={used} aria-valuemax={limit} style={{ width: 70, height: 70, borderRadius: "50%", display: "grid", placeItems: "center", border: "1px solid var(--ink-faint)", background: `conic-gradient(var(--ink) ${percent}%, var(--wash) ${percent}% 100%)` }}>
      <span style={{ width: 52, height: 52, borderRadius: "50%", display: "grid", placeItems: "center", background: "var(--paper-raised)", color: "var(--ink-strong)", font: "12px var(--font-mono)" }}>{percent}%</span>
    </div>
    <div style={{ display: "grid", gap: 4 }}><strong style={{ fontFamily: "var(--font-seal)", fontWeight: 500 }}>预算墨池</strong><span style={{ color: "var(--ink-mid)", font: "12px var(--font-mono)" }}>{used.toLocaleString()} / {limit.toLocaleString()} tokens</span>{ratio >= 1 && <span style={{ color: "var(--cinnabar)", fontSize: 12 }}>预算已阻塞下一节点。</span>}</div>
  </section>;
}
