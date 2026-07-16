export function WorkflowStatus({ status, onAction }: { status: string; onAction: (action: "pause" | "resume" | "cancel" | "retry") => void }) {
  return <section className="workflow-status" aria-label="Workflow status"><strong>{status}</strong><div><button onClick={() => onAction("pause")}>Pause</button><button onClick={() => onAction("resume")}>Resume</button><button onClick={() => onAction("cancel")}>Cancel</button><button onClick={() => onAction("retry")}>Retry</button></div></section>;
}
