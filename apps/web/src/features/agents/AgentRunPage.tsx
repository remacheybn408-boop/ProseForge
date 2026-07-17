import { AgentGraphView } from "./AgentGraphView";
import { AgentRunControls } from "./AgentRunControls";
import { AgentTaskTable } from "./AgentTaskTable";
export function AgentRunPage({ status = "PENDING", tasks = [], onAction = () => undefined }: { status?: string; tasks?: { id: string; role: string; status: string; attempts: number }[]; onAction?: (action: "pause" | "resume" | "cancel" | "retry") => void }) { return <section className="agent-run-page"><header><h2>Agent run</h2><span className="status-stamp">{status}</span></header><AgentRunControls onAction={onAction} /><AgentGraphView tasks={tasks} /><AgentTaskTable tasks={tasks} /></section>; }
