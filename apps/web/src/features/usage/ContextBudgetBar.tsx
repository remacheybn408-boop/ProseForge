import { useLanguage } from "../../lib/i18n";

function formatCount(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1).replace(/\.0$/, "")}K`;
  return String(value);
}

export function ContextBudgetBar({ used, available, total, outputReserve = 0 }: { used: number; available: number; total: number; outputReserve?: number }) {
  const { t } = useLanguage();
  const budgetTotal = Math.max(0, total - outputReserve);
  const percent = budgetTotal > 0 ? Math.min(100, Math.round((used / budgetTotal) * 100)) : 0;
  const warning = percent >= 95 ? "contextBudget95" : percent >= 85 ? "contextBudget85" : percent >= 70 ? "contextBudget70" : undefined;
  return <section className="context-budget" aria-label={t("context")}>
    <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-label={t("context")}><span style={{ width: `${percent}%` }} /></div>
    <div><span>{formatCount(used)} {t("used")}</span><span>{formatCount(available)} {t("available")}</span>{outputReserve > 0 && <span>{formatCount(outputReserve)} {t("outputReserve")}</span>}</div>
    {warning && <p role="status" aria-live="polite">{t(warning)}</p>}
  </section>;
}
