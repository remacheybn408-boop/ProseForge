import { WorkflowBudgetPanel } from "./WorkflowBudgetPanel";
import { WorkflowCanvas, type CanvasNode } from "./WorkflowCanvas";
import { WorkflowRunTimeline } from "./WorkflowRunTimeline";
export function WorkflowStudioPage({ nodes, events, used = 0, limit = 1 }: { nodes: CanvasNode[]; events: { id: string; label: string; status: string }[]; used?: number; limit?: number }) { return <section className="workflow-studio"><WorkflowCanvas nodes={nodes} /><WorkflowBudgetPanel used={used} limit={limit} /><WorkflowRunTimeline events={events} /></section>; }
