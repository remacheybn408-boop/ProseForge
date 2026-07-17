import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../../lib/i18n";
import { WorkflowView } from "./WorkflowView";

vi.mock("../../lib/api/client", () => ({
  controlWorkflow: vi.fn(),
  subscribeWorkflowEvents: vi.fn(() => Promise.resolve()),
}));

const project = { id: "project-1", slug: "project", title: "The Archive", genre: "", style: "", language: "en-US", status: "ACTIVE" };
const workflow = {
  id: "workflow-1",
  project_id: "project-1",
  workflow_type: "NOVEL",
  status: "RUNNING",
  current_step: "CHAPTER_2_DRAFTING",
  completed_steps: ["context", "chapter_1"],
  chapter_progress: { current: 2, completed: [1], total: 3, requested: [1, 2, 3] },
  retry_count: 2,
  model: "writer-model",
  editor_model: "editor-model",
  token_cost_estimate: { used_tokens: 120, token_limit: 1000, cost_usd: 0.42, cost_limit: 1 },
} as never;

describe("WorkflowView", () => {
  it("shows durable workflow progress and model-aware budget details", () => {
    localStorage.setItem("proseforge.web.language", "en-US");
    render(<LanguageProvider><WorkflowView project={project} workflow={workflow} onWorkflow={() => undefined} /></LanguageProvider>);

    const details = screen.getByRole("region", { name: "Workflow details" });
    expect(details.textContent).toContain("CHAPTER_2_DRAFTING");
    expect(details.textContent).toContain("context, chapter_1");
    expect(details.textContent).toContain("1 of 3 Chapters");
    expect(details.textContent).toContain("writer-model");
    expect(details.textContent).toContain("120 / 1000");
    expect(details.textContent).toContain("$0.42 / $1.00");
  });
});
