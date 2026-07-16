import { useUsageSummaryQuery } from "../../app/query";
import { TokenMeter } from "./TokenMeter";
import { PaperPanel } from "../../components/ink/Ink";
import { useLanguage } from "../../lib/i18n";

export function UsagePage({ projectId }: { projectId?: string }) {
  const { t } = useLanguage();
  const query = useUsageSummaryQuery(projectId);
  if (query.isPending) return <section className="detail-view"><p>{t("usageLoading")}</p></section>;
  if (query.isError || !query.data) return <section className="detail-view"><p role="alert">{t("usageUnavailable")}</p></section>;
  const { actual, estimated } = query.data;
  return <section className="detail-view usage-page"><div className="detail-heading"><p className="eyebrow">{t("usageTitle")}</p><h2>{t("usageTitle")}</h2><p>{t("usageDescription")}</p></div><PaperPanel><TokenMeter actual={actual.total_tokens} estimated={estimated.total_tokens} cost={actual.cost_usd} /></PaperPanel><div className="usage-grid"><div><strong>{actual.input_tokens.toLocaleString()}</strong><span>{t("actualInput")}</span></div><div><strong>{actual.output_tokens.toLocaleString()}</strong><span>{t("actualOutput")}</span></div><div><strong>{estimated.total_tokens.toLocaleString()}</strong><span>{t("estimatedTotal")}</span></div></div></section>;
}
