import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { describe, expect, it } from "vitest";
import { routeTree } from "./routes";

function loadRouter(initialPath: string) {
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: [initialPath] }) });
  return router.load().then(() => router);
}

describe("workspace route tree", () => {
  it("redirects the index to the projects list", async () => {
    const router = await loadRouter("/");
    expect(router.state.location.pathname).toBe("/projects");
  });

  it("resolves the chat workspace route with conversation and branch params", async () => {
    const router = await loadRouter("/projects/p1/chat/c1/main");
    const leaf = router.state.matches.at(-1);
    expect(leaf?.routeId).toBe("/projects/$projectId/chat/$conversationId/$branchId");
    expect(leaf?.params).toMatchObject({ projectId: "p1", conversationId: "c1", branchId: "main" });
  });

  it("resolves the manuscript route with the chapter param", async () => {
    const router = await loadRouter("/projects/p1/manuscript/ch7");
    const leaf = router.state.matches.at(-1);
    expect(leaf?.routeId).toBe("/projects/$projectId/manuscript/$chapterId");
    expect(leaf?.params).toMatchObject({ projectId: "p1", chapterId: "ch7" });
  });

  it("resolves review, workflow and settings routes", async () => {
    const review = await loadRouter("/projects/p1/review/r9");
    expect(review.state.matches.at(-1)?.routeId).toBe("/projects/$projectId/review/$reportId");
    const workflow = await loadRouter("/projects/p1/workflows/w2");
    expect(workflow.state.matches.at(-1)?.routeId).toBe("/projects/$projectId/workflows/$workflowId");
    const settings = await loadRouter("/settings/models");
    expect(settings.state.matches.at(-1)?.routeId).toBe("/settings/models");
  });

  it("carries the V1 studio and outline views as project routes", async () => {
    const studio = await loadRouter("/projects/p1/studio");
    expect(studio.state.matches.at(-1)?.routeId).toBe("/projects/$projectId/studio");
    const outline = await loadRouter("/projects/p1/outline");
    expect(outline.state.matches.at(-1)?.routeId).toBe("/projects/$projectId/outline");
  });
});
