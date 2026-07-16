import { useUsageSummaryQuery } from "../../app/query";
import { TokenMeter } from "./TokenMeter";
import { PaperPanel } from "../../components/ink/Ink";

export function UsagePage({ projectId }: { projectId?: string }) {
  const query = useUsageSummaryQuery(projectId);
  if (query.isPending) return <section className="detail-view"><p>Loading usage…</p></section>;
  if (query.isError || !query.data) return <section className="detail-view"><p role="alert">Usage is unavailable right now.</p></section>;
  const { actual, estimated } = query.data;
  return <section className="detail-view usage-page"><div className="detail-heading"><p className="eyebrow">USAGE</p><h2>Token usage</h2><p>Actual provider usage and local estimates stay visibly separate.</p></div><PaperPanel><TokenMeter actual={actual.total_tokens} estimated={estimated.total_tokens} cost={actual.cost_usd} /></PaperPanel><div className="usage-grid"><div><strong>{actual.input_tokens.toLocaleString()}</strong><span>Actual input</span></div><div><strong>{actual.output_tokens.toLocaleString()}</strong><span>Actual output</span></div><div><strong>{estimated.total_tokens.toLocaleString()}</strong><span>Estimated total</span></div></div></section>;
}
