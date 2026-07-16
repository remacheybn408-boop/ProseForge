import { useEffect, useState } from "react";
import { controlWorkflow, subscribeWorkflowEvents, type Project, type Workflow } from "../../lib/api/client";
import { useLanguage } from "../../lib/i18n";
import { canApplyWorkflowAction } from "./WorkflowStatus";

export function WorkflowView({ project, workflow, onWorkflow }: { project: Project; workflow: Workflow | null; onWorkflow: (workflow: Workflow) => void }) {
  const { t } = useLanguage();
  const [current, setCurrent] = useState(workflow);
  const [message, setMessage] = useState(t("workflowNotStarted"));

  useEffect(() => {
    if (workflow) setCurrent(workflow);
  }, [workflow]);

  useEffect(() => {
    if (!current) return;
    const controller = new AbortController();
    const workflowSnapshot = current;
    subscribeWorkflowEvents(current.id, event => {
      const status = typeof event.data.status === "string" ? event.data.status : event.event;
      if (!status) return;
      const next = { ...workflowSnapshot, status };
      setCurrent(next);
      onWorkflow(next);
    }, { signal: controller.signal }).catch(() => {
      if (!controller.signal.aborted) setMessage(t("workflowEventsUnavailable"));
    });
    return () => controller.abort();
  }, [current?.id, onWorkflow, t]);

  const action = async (name: "pause" | "resume" | "cancel" | "retry") => {
    if (!current) return;
    try {
      const result = await controlWorkflow(current.id, name);
      setCurrent(result);
      onWorkflow(result);
      setMessage(`${t("workflowStatus")}: ${result.status}`);
    } catch {
      setMessage(t("workflowActionUnavailable"));
    }
  };

  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">{t("workflow")}</p><h2>{current ? t("workflowHero") : t("notStarted")}</h2><p>{current ? `${project.title} · ${current.status}` : message}</p></div>{current ? <><div className="timeline"><div className="timeline-item done"><b>1</b><div><strong>{t("outlineConfirmed")}</strong><span>{t("savedToPostgres")}</span></div></div><div className="timeline-item current"><b>2</b><div><strong>{t("draftChapter")}</strong><span>{current.status}</span></div></div><div className="timeline-item"><b>3</b><div><strong>{t("reviewCommit")}</strong><span>{t("waiting")}</span></div></div></div><div className="workflow-actions"><button disabled={!canApplyWorkflowAction(current.status, "pause")} onClick={() => action("pause")}>{t("pause")}</button><button disabled={!canApplyWorkflowAction(current.status, "resume")} onClick={() => action("resume")}>{t("resume")}</button><button disabled={!canApplyWorkflowAction(current.status, "cancel")} onClick={() => action("cancel")}>{t("cancel")}</button><button disabled={!canApplyWorkflowAction(current.status, "retry")} onClick={() => action("retry")}>{t("retry")}</button></div></> : <p className="form-message">{t("outlineIntake")}</p>}</section>;
}
