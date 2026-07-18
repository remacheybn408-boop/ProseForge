export function ReviewPage({ reportId }: { reportId: string }) {
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">REVIEW</p><h2>Review report</h2><p>Report {reportId}. The full review surface arrives with the revision workflow task.</p></div></section>;
}
