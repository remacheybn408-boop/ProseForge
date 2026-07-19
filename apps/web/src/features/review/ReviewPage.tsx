import { useMemo, useState } from "react";
import { ReviewFilters, type ReviewEvidence, type ReviewSeverity, type ReviewSeverityFilter } from "./ReviewFilters";

export type ReviewFinding = {
  id: string;
  severity: ReviewSeverity;
  title: string;
  detail: string;
  evidence?: ReviewEvidence;
};

export function ReviewPage({ findings, onEvidenceJump }: {
  findings: readonly ReviewFinding[];
  onEvidenceJump?: (evidence: ReviewEvidence) => void;
}) {
  const [severity, setSeverity] = useState<ReviewSeverityFilter>("all");
  const visibleFindings = useMemo(
    () => findings.filter(finding => severity === "all" || finding.severity === severity),
    [findings, severity],
  );
  const evidence = visibleFindings.flatMap(finding => finding.evidence ? [finding.evidence] : []);

  return <section aria-label="Review findings">
    <header><p className="eyebrow">REVIEW</p><h2>Review report</h2></header>
    <ReviewFilters severity={severity} onSeverityChange={setSeverity} evidence={evidence} onEvidenceJump={onEvidenceJump} />
    {visibleFindings.length === 0 ? <p>No findings match this filter.</p> : <ol>
      {visibleFindings.map(finding => <li key={finding.id} data-severity={finding.severity}>
        <strong>{finding.severity}</strong>
        <h3>{finding.title}</h3>
        <p>{finding.detail}</p>
        {finding.evidence && <button type="button" onClick={() => onEvidenceJump?.(finding.evidence!)}>View evidence</button>}
      </li>)}
    </ol>}
  </section>;
}
