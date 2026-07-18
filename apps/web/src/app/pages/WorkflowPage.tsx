import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { controlWorkflow, getWorkflow, type Workflow } from "../../lib/api/client";
import { useProjectsQuery } from "../query";

export function WorkflowPage({ projectId, workflowId }: { projectId: string; workflowId?: string }) {
  const queryClient = useQueryClient();
  const projectsQuery = useProjectsQuery();
  const project = projectsQuery.data?.find(item => item.id === projectId);
  const workflowQuery = useQuery({ queryKey: ["workflows", workflowId], queryFn: () => getWorkflow(workflowId!), enabled: Boolean(workflowId), retry: false });
  const [current, setCurrent] = useState<Workflow | null>(null);
  const [message, setMessage] = useState("No workflow has been started yet.");
  useEffect(() => { if (workflowQuery.data) setCurrent(workflowQuery.data); }, [workflowQuery.data]);
  const action = async (name: "pause" | "resume" | "cancel" | "retry") => { if (!current) return; try { const result = await controlWorkflow(current.id, name); setCurrent(result); setMessage(`Workflow ${result.status.toLowerCase()}.`); void queryClient.invalidateQueries({ queryKey: ["workflows", current.id] }); } catch { setMessage("That action is not available in the current state."); } };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">DURABLE WORKFLOW</p><h2>{current ? "Chapter workflow" : "No active workflow"}</h2><p>{current ? `Project: ${project?.title ?? projectId} · ${current.status}` : message}</p></div>{current ? <><div className="timeline"><div className="timeline-item done"><b>1</b><div><strong>Outline confirmed</strong><span>Saved to PostgreSQL</span></div></div><div className="timeline-item current"><b>2</b><div><strong>Draft chapter</strong><span>{current.status}</span></div></div><div className="timeline-item"><b>3</b><div><strong>Review and commit</strong><span>Waiting</span></div></div></div><div className="workflow-actions"><button onClick={() => action("pause")}>Pause</button><button onClick={() => action("resume")}>Resume</button><button onClick={() => action("cancel")}>Cancel</button><button onClick={() => action("retry")}>Retry</button></div></> : <p className="form-message">Open Outline Intake to start a workflow.</p>}</section>;
}
