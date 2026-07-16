type WorkflowAction = "pause" | "resume" | "cancel" | "retry";
import { useLanguage } from "../../lib/i18n";

const allowedTransitions: Record<string, string[]> = {
  CREATED: ["CANCELLED", "QUEUED"], WAITING_USER: ["CANCELLED", "QUEUED"], QUEUED: ["CANCELLED", "RUNNING"],
  RUNNING: ["PAUSED", "CANCELLED", "RETRYING"], PAUSED: ["QUEUED", "CANCELLED"], RETRYING: ["PAUSED"],
  RECOVERING: ["QUEUED", "PAUSED"], FAILED: ["QUEUED"], BUDGET_BLOCKED: ["QUEUED", "CANCELLED"],
};

export function canApplyWorkflowAction(status: string, action: WorkflowAction): boolean {
  const target = action === "pause" ? "PAUSED" : action === "cancel" ? "CANCELLED" : allowedTransitions[status]?.includes("QUEUED") ? "QUEUED" : "RETRYING";
  return allowedTransitions[status]?.includes(target) ?? false;
}

export function WorkflowStatus({ status, onAction }: { status: string; onAction: (action: WorkflowAction) => void }) {
  const { t } = useLanguage();
  return <section className="workflow-status" aria-label={t("workflowStatus")}><strong>{status}</strong><div>{(["pause", "resume", "cancel", "retry"] as WorkflowAction[]).map(action => <button key={action} disabled={!canApplyWorkflowAction(status, action)} onClick={() => onAction(action)}>{t(action)}</button>)}</div></section>;
}
