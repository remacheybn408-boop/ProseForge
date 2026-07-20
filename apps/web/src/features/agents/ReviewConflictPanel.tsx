import type { AgentReview } from "../../lib/api/client";

function evidenceSummary(evidence: Record<string, unknown>) {
  return Object.entries(evidence).map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`).join(" · ");
}

// Reviews are listed with a dual-encoded status stamp. A conflicting entry
// (status CONFLICT or a shared conflict_group) is marked with the tilted 8°
// cinnabar-outlined seal and can be handed to the V2 proposal flow — the hand-off
// never writes a ChapterVersion directly.
export function ReviewConflictPanel({ reviews, onSelect }: { reviews: AgentReview[]; onSelect?: (reviewId: string) => void }) {
  return <section aria-label="Reviews" className="review-panel" style={{ display: "grid", gap: 8 }}>
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <strong style={{ fontFamily: "var(--font-seal)", fontWeight: 500 }}>Reviews</strong>
      <span style={{ color: "var(--ink-mid)", font: "11px var(--font-mono)" }}>{reviews.length} recorded</span>
    </header>
    {reviews.map(review => {
      const conflicting = review.status === "CONFLICT" || Boolean(review.conflict_group);
      return <article key={review.id} className={"review-item" + (conflicting ? " review-item-conflict" : "")}>
        {conflicting
          ? <span className="conflict-seal" aria-label="Conflict seal" title="Conflict" style={{ transform: "rotate(-8deg)" }}>冲</span>
          : <span className="status-stamp" data-status={review.status}>{review.status}</span>}
        <div className="review-item-body">
          <strong>{review.reviewer_role}</strong>
          <span className="review-status-text">{review.status}</span>
          {review.conflict_group && <small>conflict group: {review.conflict_group}</small>}
          {review.evidence.length > 0 && <ul>{review.evidence.map((item, index) => <li key={index}>{evidenceSummary(item)}</li>)}</ul>}
          {conflicting && <button type="button" aria-label={"Send review " + review.id + " to proposal"} onClick={() => onSelect?.(review.id)}>Send to proposal</button>}
        </div>
      </article>;
    })}
    {!reviews.length && <p className="agent-empty">No reviews recorded yet.</p>}
  </section>;
}
