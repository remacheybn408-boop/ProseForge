import type { BranchCompareEntry, BranchCompareResult } from "../../lib/api/client";

export type ComparePrefixMessage = { id: string; role: string; content: string };

function CompareColumn({ label, entries }: { label: string; entries: BranchCompareEntry[] }) {
  return <div className="branch-compare-column" aria-label={`${label} branch`}>
    <h4>{label}</h4>
    {entries.length === 0 ? <p className="branch-compare-empty">No divergent messages</p> : <ol>
      {entries.map(entry => <li key={entry.id} className="branch-compare-message">
        <span className="branch-compare-role">{entry.role}</span>
        <p>{entry.content}</p>
        {entry.generation_attempt > 1 && <span className="branch-compare-attempt">attempt {entry.generation_attempt}</span>}
      </li>)}
    </ol>}
  </div>;
}

export function BranchCompareView({ result, leftLabel, rightLabel, prefix = [] }: {
  result: BranchCompareResult;
  leftLabel: string;
  rightLabel: string;
  prefix?: ComparePrefixMessage[];
}) {
  return <section className="branch-compare" aria-label="Branch comparison">
    <p className="branch-compare-summary">{result.common_count} shared {result.common_count === 1 ? "message" : "messages"}</p>
    {prefix.length > 0 && <ol className="branch-compare-prefix">
      {prefix.map(message => <li key={message.id} className="branch-compare-message dimmed">
        <span className="branch-compare-role">{message.role}</span>
        <p>{message.content}</p>
      </li>)}
    </ol>}
    <div className="branch-compare-columns">
      <CompareColumn label={leftLabel} entries={result.left} />
      <CompareColumn label={rightLabel} entries={result.right} />
    </div>
  </section>;
}
