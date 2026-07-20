import { useEffect, useState } from "react";
import { controlAgentRun, createAgentRun, getAgentRun, listAgentTasks, type AgentRun, type AgentTask } from "../../lib/api/client";
import { AgentRunPage, type AgentRunAction } from "../../features/agents/AgentRunPage";
import { useProjectsQuery } from "../query";

export function AgentsPage({ projectId }: { projectId: string }) {
  const projectsQuery = useProjectsQuery();
  const project = projectsQuery.data?.find(item => item.id === projectId);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [message, setMessage] = useState("Start a durable agent run for this project.");
  const refresh = async (runId: string) => {
    const [next, nextTasks] = await Promise.all([getAgentRun(runId), listAgentTasks(runId)]);
    setRun(next);
    setTasks(nextTasks);
  };
  const start = async () => {
    try {
      // A fresh idempotency key per click: reusing a fixed key makes the server
      // replay the first run instead of starting a new one.
      const idempotencyKey = `ui-${projectId}-${Date.now()}`;
      const next = await createAgentRun(projectId, { goal: "Draft and review the next scene for " + (project?.title ?? "this project") }, idempotencyKey);
      await refresh(next.id);
      setMessage("Run created; tasks are checkpointed in PostgreSQL.");
    } catch { setMessage("Could not start the agent run."); }
  };
  const action = async (name: AgentRunAction) => {
    if (!run) return;
    try {
      const next = await controlAgentRun(run.id, name);
      await refresh(next.id);
      setMessage("Run " + next.status.toLowerCase() + ".");
    } catch { setMessage("That action is not available in the current state."); }
  };
  const retryTask = async (taskId: string) => {
    if (!run) return;
    try {
      const next = await controlAgentRun(run.id, "retry", { taskId });
      await refresh(next.id);
      setMessage("Task re-queued; run " + next.status.toLowerCase() + ".");
    } catch { setMessage("That task cannot be retried in the current state."); }
  };
  useEffect(() => { setRun(null); setTasks([]); }, [projectId]);
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">V3 AGENT SWARM</p><h2>Agent orchestration</h2><p>{message}</p></div>{run ? <AgentRunPage run={run} tasks={tasks} onAction={action} onRetryTask={retryTask} onSelectConflict={reviewId => setMessage("Review " + reviewId.slice(0, 8) + " marked for the V2 proposal flow.")} /> : <button className="primary" onClick={start}>Start agent run</button>}</section>;
}
