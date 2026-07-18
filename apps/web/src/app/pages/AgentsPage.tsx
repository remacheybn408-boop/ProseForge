import { useEffect, useState } from "react";
import { controlAgentRun, createAgentRun, getAgentRun, listAgentTasks, type AgentRun, type AgentTask } from "../../lib/api/client";
import { AgentRunPage } from "../../features/agents/AgentRunPage";
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
      const next = await createAgentRun(projectId, { goal: "Draft and review the next scene for " + (project?.title ?? "this project") }, "ui-" + projectId);
      await refresh(next.id);
      setMessage("Run created; tasks are checkpointed in PostgreSQL.");
    } catch { setMessage("Could not start the agent run."); }
  };
  const action = async (name: "pause" | "resume" | "cancel" | "retry") => {
    if (!run) return;
    try {
      const next = await controlAgentRun(run.id, name);
      await refresh(next.id);
      setMessage("Run " + next.status.toLowerCase() + ".");
    } catch { setMessage("That action is not available in the current state."); }
  };
  useEffect(() => { setRun(null); setTasks([]); }, [projectId]);
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">V3 AGENT SWARM</p><h2>Agent orchestration</h2><p>{message}</p></div>{run ? <AgentRunPage status={run.status} tasks={tasks.map(task => ({ id: task.id, role: task.role, status: task.status, attempts: task.attempts }))} onAction={action} /> : <button className="primary" onClick={start}>Start agent run</button>}</section>;
}
