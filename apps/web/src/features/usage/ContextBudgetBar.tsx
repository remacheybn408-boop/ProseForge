function formatCount(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1).replace(/\.0$/, "")}K`;
  return String(value);
}

export function ContextBudgetBar({ used, available, total }: { used: number; available: number; total: number }) {
  const percent = total > 0 ? Math.min(100, Math.round((used / total) * 100)) : 0;
  return <section className="context-budget" aria-label="Context budget"><div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-label="Context budget"><span style={{ width: `${percent}%` }} /></div><div><span>{formatCount(used)} used</span><span>{formatCount(available)} available</span></div></section>;
}
