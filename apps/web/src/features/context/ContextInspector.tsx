import { EmptyScroll, PaperPanel, SealBadge } from "../../components/ink/Ink";

export type ContextBlock = {
  source_type: string;
  source_id: string;
  text?: string;
  token_estimate: number;
  priority?: number;
  pinned?: boolean;
  redaction?: boolean;
  reason?: string;
};

export type OmittedContextBlock = {
  source_id?: string;
  source_type?: string;
  message_id?: string;
  reason: string;
  token_estimate?: number;
};

export type ContextSnapshot = {
  id: string;
  snapshot_hash: string;
  payload: {
    blocks?: ContextBlock[];
    omitted?: OmittedContextBlock[];
    budget?: { context_window: number; input_tokens: number; output_reserve: number };
    injected_fact_ids?: string[];
  };
};

function humanize(reason: string): string {
  return reason.replace(/_/g, " ");
}

function tokenCount(value?: number): string {
  return (value ?? 0).toLocaleString();
}

export function ContextInspector({ snapshot }: { snapshot?: ContextSnapshot | null }) {
  if (!snapshot) return <EmptyScroll><p className="empty-scroll-title">No context snapshot</p><p className="empty-scroll-hint">Generate a reply to inspect exactly which facts and messages were considered.</p></EmptyScroll>;
  const blocks = snapshot.payload.blocks ?? [];
  const omitted = snapshot.payload.omitted ?? [];
  const budget = snapshot.payload.budget;
  const injectedIds = new Set(snapshot.payload.injected_fact_ids ?? []);
  return <section className="context-inspector" aria-label="Context Inspector">
    <header><p className="eyebrow">CONTEXT INSPECTOR</p><h3>Generation snapshot</h3><code title={snapshot.snapshot_hash}>{snapshot.id}</code></header>
    {budget ? <PaperPanel className="context-budget-summary"><h3>Token budget</h3><dl><div><dt>Input</dt><dd>{tokenCount(budget.input_tokens)}</dd></div><div><dt>Reserve</dt><dd>{tokenCount(budget.output_reserve)}</dd></div><div><dt>Window</dt><dd>{tokenCount(budget.context_window)}</dd></div></dl></PaperPanel> : null}
    <section className="context-section"><h4>Included context</h4>{blocks.length === 0 ? <p className="context-empty">No blocks were included.</p> : <ul>{blocks.map(block => <li key={`${block.source_type}-${block.source_id}`}><div><strong>{block.source_id}</strong><span>{block.source_type.replace(/_/g, " ")} · {tokenCount(block.token_estimate)} tokens</span>{block.reason ? <span>Reason: {humanize(block.reason)}</span> : null}</div><div>{block.pinned ? <SealBadge tone="success">PIN</SealBadge> : null}{injectedIds.has(block.source_id) ? <SealBadge>USED</SealBadge> : null}</div></li>)}</ul>}</section>
    <section className="context-section"><h4>Omitted context</h4>{omitted.length === 0 ? <p className="context-empty">Nothing was omitted.</p> : <ul>{omitted.map(block => {
      const sourceId = block.source_id ?? block.message_id ?? "unknown source";
      return <li key={`${block.source_type ?? "context"}-${sourceId}`}><div><strong>{sourceId}</strong><span>{block.source_type?.replace(/_/g, " ") ?? "context"}</span></div><span className="context-omit-reason">{humanize(block.reason)}</span></li>;
    })}</ul>}</section>
  </section>;
}
