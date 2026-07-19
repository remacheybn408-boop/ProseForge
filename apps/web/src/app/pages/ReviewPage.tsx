import { useEffect, useState } from "react";
import { request } from "../../lib/api/client";
import { ReviewPage as ReviewReportPage, type ReviewFinding } from "../../features/review/ReviewPage";

type ApiFinding = { severity: "blocking" | "suggestion" | "nit"; message: string; evidence?: { from?: number; to?: number }[] };

export function ReviewPage({ reportId }: { reportId: string }) {
  const [findings, setFindings] = useState<ReviewFinding[]>([]);
  const [message, setMessage] = useState("Loading review report…");
  useEffect(() => {
    request<{ findings: ApiFinding[] }>(`/api/v2/reviews/${encodeURIComponent(reportId)}`).then(report => {
      setFindings(report.findings.map((finding, index) => ({ id: String(index), severity: finding.severity, title: finding.message, detail: finding.message, evidence: finding.evidence?.[0] ? { id: String(index), label: `Characters ${finding.evidence[0].from ?? 0}–${finding.evidence[0].to ?? 0}` } : undefined })));
      setMessage("");
    }).catch(() => setMessage("Review report could not be loaded."));
  }, [reportId]);
  if (message) return <section className="detail-view"><p aria-live="polite">{message}</p></section>;
  return <ReviewReportPage findings={findings} onEvidenceJump={() => undefined} />;
}
