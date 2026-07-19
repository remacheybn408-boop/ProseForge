export const reviewSeverities = ["blocking", "suggestion", "nit"] as const;

export type ReviewSeverity = (typeof reviewSeverities)[number];
export type ReviewSeverityFilter = ReviewSeverity | "all";

export type ReviewEvidence = {
  id: string;
  label: string;
};

export function ReviewFilters({
  severity,
  onSeverityChange,
  evidence = [],
  onEvidenceJump,
}: {
  severity: ReviewSeverityFilter;
  onSeverityChange: (severity: ReviewSeverityFilter) => void;
  evidence?: readonly ReviewEvidence[];
  onEvidenceJump?: (evidence: ReviewEvidence) => void;
}) {
  return <section aria-label="Review filters">
    <label>
      Severity
      <select aria-label="Severity" value={severity} onChange={event => onSeverityChange(event.target.value as ReviewSeverityFilter)}>
        <option value="all">All findings</option>
        {reviewSeverities.map(level => <option key={level} value={level}>{level}</option>)}
      </select>
    </label>
    {evidence.length > 0 && <div aria-label="Evidence links">
      {evidence.map(item => <button key={item.id} type="button" onClick={() => onEvidenceJump?.(item)}>
        Jump to evidence: {item.label}
      </button>)}
    </div>}
  </section>;
}
