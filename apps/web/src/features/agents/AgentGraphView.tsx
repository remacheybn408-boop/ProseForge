import type { AgentTask } from "../../lib/api/client";
import { agentRoleSeal } from "./agentQueries";

// Read-only task graph reusing the Workflow node-card conventions (seal-font title,
// status stamp at the top right); each card is stamped with the single-character
// role seal instead of an avatar. Dependencies render as an "after" line.
export function AgentGraphView({ tasks }: { tasks: AgentTask[] }) {
  return <div className="agent-graph-view" aria-label="Agent graph">
    {tasks.map(task => <div className="agent-graph-node" key={task.id}>
      <span className="role-seal" aria-label={"Role seal: " + task.role} title={task.role}>{agentRoleSeal(task.role)}</span>
      <div className="agent-graph-node-body">
        <strong>{task.task_key}</strong>
        <span className="agent-task-role">{task.role}</span>
        {task.depends_on.length > 0 && <small>after {task.depends_on.join(", ")}</small>}
      </div>
      <span className="status-stamp" data-status={task.status}>{task.status}</span>
    </div>)}
    {!tasks.length && <p className="agent-empty">No tasks in this run yet.</p>}
  </div>;
}
