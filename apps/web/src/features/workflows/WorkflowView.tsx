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
      const next = { ...workflowSnapshot, ...(event.data as Partial<Workflow>), status };
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

  const progress = current?.chapter_progress ?? { current: null, completed: [], total: 0, requested: [] };
  const steps = current?.completed_steps ?? [];
  const currentStep = current?.current_step ?? current?.checkpoint ?? current?.status ?? t("noCurrentStep");
  const budget = current?.token_cost_estimate ?? { used_tokens: current?.used_tokens ?? 0, token_limit: current?.token_limit ?? 0, cost_usd: current?.estimated_cost ?? 0, cost_limit: current?.cost_limit ?? 0 };
  const cost = (value: number) => `$${value.toFixed(2)}`;

  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">{t("workflow")}</p><h2>{current ? t("workflowHero") : t("notStarted")}</h2><p>{current ? `${project.title} · ${current.status}` : message}</p></div>{current ? <>
    <section className="workflow-details" aria-label={t("workflowDetails")}>
      <dl className="workflow-metrics">
        <div><dt>{t("currentStep")}</dt><dd>{currentStep}</dd></div>
        <div><dt>{t("completedSteps")}</dt><dd>{steps.length ? steps.join(", ") : t("noCompletedSteps")}</dd></div>
        <div><dt>{t("chapterProgress")}</dt><dd>{progress.completed.length} {t("of")} {progress.total} {t("chapters")}{progress.current === null ? "" : ` · ${t("currentChapter")} ${progress.current}`}</dd></div>
        <div><dt>{t("retryCount")}</dt><dd>{current.retry_count ?? 0}</dd></div>
        <div><dt>{t("model")}</dt><dd>{current.model ?? t("unknown")}{current.editor_model ? ` · ${current.editor_model}` : ""}</dd></div>
        <div><dt>{t("tokenEstimate")}</dt><dd>{budget.used_tokens} / {budget.token_limit || "∞"}</dd></div>
        <div><dt>{t("costEstimate")}</dt><dd>{cost(budget.cost_usd)} / {budget.cost_limit ? cost(budget.cost_limit) : "∞"}</dd></div>
      </dl>
    </section>
    <div className="timeline">{steps.length > 0 ? steps.map((step, index) => <div className="timeline-item done" key={step}><b>{index + 1}</b><div><strong>{step}</strong><span>{t("completed")}</span></div></div>) : <div className="timeline-item current"><b>1</b><div><strong>{currentStep}</strong><span>{current.status}</span></div></div>}<div className="timeline-item current"><b>{steps.length + 1}</b><div><strong>{currentStep}</strong><span>{current.status}</span></div></div></div>
    <div className="workflow-actions"><button disabled={!canApplyWorkflowAction(current.status, "pause")} onClick={() => action("pause")}>{t("pause")}</button><button disabled={!canApplyWorkflowAction(current.status, "resume")} onClick={() => action("resume")}>{t("resume")}</button><button disabled={!canApplyWorkflowAction(current.status, "cancel")} onClick={() => action("cancel")}>{t("cancel")}</button><button disabled={!canApplyWorkflowAction(current.status, "retry")} onClick={() => action("retry")}>{t("retry")}</button></div>
  </> : <p className="form-message">{t("outlineIntake")}</p>}</section>;
}
