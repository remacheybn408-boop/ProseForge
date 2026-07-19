import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { WorkflowNodeState } from "../../lib/api/client";
import { WorkflowBudgetPanel } from "./WorkflowBudgetPanel";
import { connectionCreatesCycle, type CanvasEdge, type CanvasNode, type WorkflowNodeKind } from "./WorkflowCanvas";
import { applyNodeStates, canvasGraphEqual, fromApiDefinition, isTerminalWorkflowRun, isWorkflowRunReadOnly, mergeWorkflowEvents, toApiDefinition, toCanvasNodeStatus } from "./workflowQueries";

const canvasNode = (id: string, kind: WorkflowNodeKind, x = 0, y = 0): CanvasNode => ({ id, type: "workflow", position: { x, y }, data: { kind, label: `标题-${id}`, summary: `摘要-${id}`, status: "pending", params: {} } });
const nodeState = (nodeKey: string, status: string): WorkflowNodeState => ({ id: `state-${nodeKey}`, node_key: nodeKey, status, retry_count: 0, reserved_tokens: 0, used_tokens: 0, reserved_cost: 0, used_cost: 0 });

describe("Workflow Studio primitives", () => {
  it("rejects a connection that closes a cycle", () => {
    expect(connectionCreatesCycle([{ id: "a-b", source: "a", target: "b" }, { id: "b-c", source: "b", target: "c" }], "c", "a")).toBe(true);
    expect(connectionCreatesCycle([{ id: "a-b", source: "a", target: "b" }], "b", "c")).toBe(false);
  });

  it("uses the same value for the ink pool and budget text", () => {
    render(<WorkflowBudgetPanel used={40} limit={100} />);
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("40");
    expect(screen.getByText("40 / 100 tokens")).toBeTruthy();
  });

  it("locks a running workflow and preserves a replay-free event timeline", () => {
    expect(isWorkflowRunReadOnly("RUNNING")).toBe(true);
    expect(isWorkflowRunReadOnly("PAUSED")).toBe(false);
    expect(isTerminalWorkflowRun("COMPLETED")).toBe(true);
    expect(isTerminalWorkflowRun("RUNNING")).toBe(false);
    expect(mergeWorkflowEvents([{ id: "1", label: "started", status: "RUNNING" }], [{ id: "1", label: "started", status: "RUNNING" }, { id: "2", label: "done", status: "DONE" }]).map(event => event.id)).toEqual(["1", "2"]);
  });

  it("maps canvas nodes to the API shape the backend validator accepts", () => {
    const edges: CanvasEdge[] = [{ id: "a-b", source: "a", target: "b" }];
    const api = toApiDefinition([canvasNode("a", "intake", 12.4, 30.6), canvasNode("b", "write")], edges);
    expect(api.nodes).toEqual([
      { id: "a", kind: "intake", title: "标题-a", summary: "摘要-a", position: { x: 12, y: 31 } },
      { id: "b", kind: "write", title: "标题-b", summary: "摘要-b", position: { x: 0, y: 0 } },
    ]);
    expect(api.edges).toEqual([{ source: "a", target: "b" }]);
  });

  it("maps saved definitions back onto the canvas with a deterministic layout", () => {
    const { nodes, edges } = fromApiDefinition({
      nodes: [
        { id: "a", kind: "intake", title: "素材接入", summary: "读入素材", position: { x: 5, y: 7 } },
        { id: "b", kind: "write" },
        { id: "c", kind: "export" },
      ],
      edges: [{ source: "a", target: "b" }, { source: "b", target: "c" }, { source: "a", target: "ghost" }],
    });
    expect(edges).toEqual([{ id: "a-b", source: "a", target: "b" }, { id: "b-c", source: "b", target: "c" }]);
    const byId = new Map(nodes.map(node => [node.id, node]));
    expect(byId.get("a")?.position).toEqual({ x: 5, y: 7 });
    expect(byId.get("a")?.data).toMatchObject({ kind: "intake", label: "素材接入", summary: "读入素材", status: "pending" });
    expect(byId.get("b")?.data.kind).toBe("write");
    // No stored position -> layered layout: depth grows along edges, so columns move right.
    const ax = byId.get("a")?.position.x ?? 0;
    expect(byId.get("b")?.position.x).toBeGreaterThan(ax);
    expect(byId.get("c")?.position.x).toBeGreaterThan(byId.get("b")?.position.x ?? 0);
    expect(fromApiDefinition({ nodes: [{ id: "x", kind: "plan" }], edges: [] })).toEqual(fromApiDefinition({ nodes: [{ id: "x", kind: "plan" }], edges: [] }));
  });

  it("maps backend node states onto canvas node statuses", () => {
    expect(toCanvasNodeStatus("PENDING")).toBe("pending");
    expect(toCanvasNodeStatus("RUNNING")).toBe("running");
    expect(toCanvasNodeStatus("COMPLETED")).toBe("done");
    expect(toCanvasNodeStatus("FAILED")).toBe("failed");
    expect(toCanvasNodeStatus("BLOCKED")).toBe("blocked");
    expect(toCanvasNodeStatus("SOMETHING_NEW")).toBe("pending");
    const mapped = applyNodeStates([canvasNode("a", "intake"), canvasNode("b", "write")], [nodeState("a", "COMPLETED"), nodeState("b", "RUNNING")]);
    expect(mapped.map(node => node.data.status)).toEqual(["done", "running"]);
  });

  it("treats structurally identical graphs as equal to break the sync loop", () => {
    const left = { nodes: [canvasNode("a", "intake", 10, 20)], edges: [{ id: "a-b", source: "a", target: "b" }] as CanvasEdge[] };
    expect(canvasGraphEqual(left, { nodes: [canvasNode("a", "intake", 10, 20)], edges: [{ id: "other-id", source: "a", target: "b" }] })).toBe(true);
    expect(canvasGraphEqual(left, { nodes: [canvasNode("a", "intake", 11, 20)], edges: left.edges })).toBe(false);
    expect(canvasGraphEqual(left, { nodes: [canvasNode("a", "intake", 10, 20)], edges: [] })).toBe(false);
  });
});
