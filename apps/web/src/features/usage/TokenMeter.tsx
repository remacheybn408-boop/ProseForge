import type { ReactNode } from "react";
import { useLanguage } from "../../lib/i18n";

function formatCount(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1).replace(/\.0$/, "")}K`;
  return String(value);
}

export function TokenMeter({ actual, estimated, limit, cost, children }: { actual: number; estimated: number; limit?: number; cost?: number | null; children?: ReactNode }) {
  const { t } = useLanguage();
  const total = actual + estimated;
  const max = limit || Math.max(total, 1);
  const percent = Math.min(100, Math.round((total / max) * 100));
  return <section className="token-meter" aria-label={t("tokenUsage")}><meter aria-label={t("tokenUsage")} min={0} max={100} value={percent} /><div className="token-meter-values"><span>{formatCount(actual)} {t("actual")}</span><span>{formatCount(estimated)} {t("estimated")}</span>{limit !== undefined && <span>{formatCount(limit)} {t("limit")}</span>}{cost == null ? <span>{t("costUnavailable")}</span> : <span>${cost.toFixed(2)}</span>}</div>{children}</section>;
}
