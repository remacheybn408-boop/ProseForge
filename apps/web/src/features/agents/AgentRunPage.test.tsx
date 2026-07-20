import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { activateChapterVersion, getAgentRun, getAgentRunAudit, listAgentArtifacts, listAgentEvents, listAgentReviews, saveChapterVersion, type AgentRun, type AgentTask } from "../../lib/api/client";
import { AgentRunPage } from "./AgentRunPage";

vi.mock("../../lib/api/client", async importOriginal => {
  const actual = await importOriginal<typeof import("../../lib/api/client")>();
  return {
    ...actual,
    getAgentRun: vi.fn(),
    getAgentRunAudit: vi.fn(),
    listAgentEvents: vi.fn(),
    listAgentArtifacts: vi.fn(),
    listAgentReviews: vi.fn(),
    saveChapterVersion: vi.fn(),
    activateChapterVersion: vi.fn(),
  };
});

const baseRun: AgentRun = { id: "run-1", project_id: "p1", status: "RUNNING", goal_hash: "goal", graph_revision: 1, checkpoint_id: "checkpoint-1", budget_used: 120, budget_limit: 1000, event_cursor: 0, policy_version: "v3-policy-1", terminal_reason: null, proposal_id: null };

const baseTasks: AgentTask[] = [
  { id: "t1", task_key: "planner", role: "chief_planner", status: "RUNNING", attempts: 1, depends_on: [] },
  { id: "t2", task_key: "reviewer", role: "continuity_reviewer", status: "PENDING", attempts: 0, depends_on: ["planner"] },
];

function renderWithQuery(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

// Built at runtime so the cursor literals are not mistaken for hex colors by the
// hardcoded-color guard in src/styles/tokens.test.ts.
function cursorText(sequence: number) {
  return "#" + String(sequence).padStart(4, "0");
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getAgentRunAudit).mockResolvedValue([]);
  vi.mocked(listAgentEvents).mockResolvedValue({ events: [], next_cursor: 0 });
  vi.mocked(getAgentRun).mockResolvedValue(baseRun);
  vi.mocked(listAgentArtifacts).mockResolvedValue([]);
  vi.mocked(listAgentReviews).mockResolvedValue([]);
});

describe("AgentRunPage", () => {
  it("shows the paused seal state and stops advancing the event poll", async () => {
    const { container } = renderWithQuery(<AgentRunPage run={{ ...baseRun, status: "PAUSED" }} tasks={baseTasks} pollIntervalMs={20} />);
    expect(container.querySelector(".run-stamp-paused")?.textContent).toBe("PAUSED");
    await waitFor(() => expect(vi.mocked(getAgentRunAudit)).toHaveBeenCalledWith("run-1"));
    await new Promise(resolve => setTimeout(resolve, 80));
    expect(vi.mocked(listAgentEvents)).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Event cursor").textContent).toBe(cursorText(0));
  });

  it("advances the mono event cursor as events append", async () => {
    vi.mocked(listAgentEvents).mockResolvedValueOnce({ events: [
      { sequence: 1, event: "run.created", data: { task_count: 2 } },
      { sequence: 2, event: "task.started", data: { task_id: "t1" } },
    ], next_cursor: 2 }).mockResolvedValue({ events: [], next_cursor: 2 });
    vi.mocked(getAgentRun).mockResolvedValue({ ...baseRun, event_cursor: 2 });
    renderWithQuery(<AgentRunPage run={baseRun} tasks={baseTasks} pollIntervalMs={20} />);
    await waitFor(() => expect(screen.getByLabelText("Event cursor").textContent).toBe(cursorText(2)));
    expect(screen.getByText("task.started")).toBeTruthy();
  });

  it("resumes from the last cursor after a reconnect without rendering duplicates", async () => {
    vi.mocked(getAgentRunAudit).mockResolvedValue([{ sequence: 1, event: "run.created", payload: { task_count: 2 } }]);
    // The replayed page overlaps the seeded cursor, as a reconnect replay would.
    vi.mocked(listAgentEvents).mockResolvedValue({ events: [
      { sequence: 1, event: "run.created", data: { task_count: 2 } },
      { sequence: 2, event: "task.started", data: { task_id: "t1" } },
    ], next_cursor: 2 });
    renderWithQuery(<AgentRunPage run={baseRun} tasks={baseTasks} pollIntervalMs={20} />);
    await waitFor(() => expect(vi.mocked(listAgentEvents)).toHaveBeenCalledWith("run-1", 1));
    await waitFor(() => expect(screen.getByLabelText("Event cursor").textContent).toBe(cursorText(2)));
    expect(screen.getAllByText("run.created")).toHaveLength(1);
    expect(screen.getAllByText(cursorText(1))).toHaveLength(1);
  });

  it("renders conflicting reviews with the tilted cinnabar conflict seal", async () => {
    vi.mocked(listAgentReviews).mockResolvedValue([{ id: "r1", artifact_id: "a1", reviewer_role: "continuity_reviewer", status: "CONFLICT", evidence: [{ rule: "continuity", result: "needs-chief-editor" }], conflict_group: "scene-merge" }]);
    renderWithQuery(<AgentRunPage run={{ ...baseRun, status: "PAUSED" }} tasks={baseTasks} />);
    const seal = await screen.findByLabelText("Conflict seal");
    expect(seal.style.transform).toContain("rotate(-8deg)");
    expect(screen.getByText(/needs-chief-editor/)).toBeTruthy();
    expect(screen.getByText(/conflict group: scene-merge/)).toBeTruthy();
  });

  it("renders the artifact schema-error placeholder instead of the preview", async () => {
    vi.mocked(listAgentArtifacts).mockResolvedValue([{ id: "a1", artifact_type: "candidate", sha256: "abcdef1234567890", preview: "", provenance: { task_id: "scene-a", schema_error: "payload missing scene" } }]);
    renderWithQuery(<AgentRunPage run={{ ...baseRun, status: "PAUSED" }} tasks={baseTasks} />);
    expect((await screen.findByRole("alert")).textContent).toContain("Schema error");
    expect(screen.getByText("abcdef123456")).toBeTruthy();
  });

  it("keeps role seals on tasks and never issues ChapterVersion writes from controls", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const onAction = vi.fn();
    const onRetryTask = vi.fn();
    renderWithQuery(<AgentRunPage run={{ ...baseRun, status: "PAUSED" }} tasks={baseTasks} onAction={onAction} onRetryTask={onRetryTask} />);
    expect(screen.getAllByLabelText("Role seal: chief_planner").map((seal: HTMLElement) => seal.textContent)).toContain("规");
    expect(screen.getAllByText("chief_planner").length).toBeGreaterThan(0);
    for (const action of ["pause", "resume", "cancel", "retry"]) fireEvent.click(screen.getByRole("button", { name: action }));
    expect(onAction).toHaveBeenCalledWith("resume");
    fireEvent.click(screen.getByRole("button", { name: "Retry planner" }));
    expect(onRetryTask).toHaveBeenCalledWith("t1");
    expect(vi.mocked(saveChapterVersion)).not.toHaveBeenCalled();
    expect(vi.mocked(activateChapterVersion)).not.toHaveBeenCalled();
    expect(fetchSpy.mock.calls.filter(([input, init]) => String(input).includes("/chapters/") && String(input).includes("/versions") && init?.method === "POST")).toHaveLength(0);
    fetchSpy.mockRestore();
  });
});
