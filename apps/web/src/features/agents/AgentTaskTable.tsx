import type { AgentTask } from "../../lib/api/client";
import { agentRoleSeal } from "./agentQueries";

// Parallel tasks are laid out as horizontal 册页 (album leaves): one leaf per task
// carrying the role seal, a dual-encoded status stamp, and the retry count.
export function AgentTaskTable({ tasks, onRetry }: { tasks: AgentTask[]; onRetry?: (taskId: string) => void }) {
  return <div className="agent-task-table" aria-label="Agent tasks">
    {tasks.map(task => <article className="agent-task-leaf" key={task.id}>
      <span className="role-seal" aria-label={"Role seal: " + task.role} title={task.role}>{agentRoleSeal(task.role)}</span>
      <div className="agent-task-leaf-body">
        <strong>{task.task_key}</strong>
        <span className="agent-task-role">{task.role}</span>
        <span className="status-stamp" data-status={task.status}>{task.status}</span>
        <small>{task.attempts} retries</small>
      </div>
      <button type="button" aria-label={"Retry " + task.task_key} onClick={() => onRetry?.(task.id)}>Retry</button>
    </article>)}
    {!tasks.length && <p className="agent-empty">No tasks in this run yet.</p>}
  </div>;
}
