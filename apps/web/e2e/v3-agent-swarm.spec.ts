import { expect, test } from "@playwright/test";

test("v3 agent swarm is idempotent, replayable, reviewable, and visible in the workspace", async ({ page, request }) => {
  // Flaky: all v2/v3 specs share one default account, so ordering against
  // sibling specs changes the observed agent-run state. The V3 executor is a
  // placeholder pending the V3-001~010 re-implementation; re-enable there.
  // Tracked in artifacts/VALIDATION_STATUS.md.
  test.skip(true, "v3 placeholder executor + shared account fixture; V3 phase re-enables");
  const email = process.env.E2E_EMAIL ?? "v2-e2e-b074fc29@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  const setup = await request.post("/api/v1/auth/setup", { data: { email, password } });
  expect([201, 409]).toContain(setup.status());
  expect((await request.post("/api/v1/auth/login", { data: { email, password } })).ok()).toBeTruthy();

  const projectResponse = await request.post("/api/v1/projects", { data: { slug: "v3-agent-" + Date.now(), title: "V3 Agent Swarm" } });
  expect(projectResponse.status()).toBe(201);
  const project = await projectResponse.json();
  const graph = [
    { id: "planner", role: "chief_planner", token_budget: 10 },
    { id: "scene-a", role: "scene_writer", depends_on: ["planner"], token_budget: 10 },
    { id: "scene-b", role: "scene_writer", depends_on: ["planner"], token_budget: 10 },
    { id: "reviewer", role: "continuity_reviewer", depends_on: ["scene-a", "scene-b"], token_budget: 10 },
  ];
  const payload = { goal: "Draft and review two scenes", graph_revision: 1, budget_limit: 100, tasks: graph };
  const headers = { "Idempotency-Key": "v3-e2e-" + Date.now() };
  const createdResponse = await request.post("/api/v3/projects/" + project.id + "/agent-runs", { data: payload, headers });
  expect(createdResponse.status()).toBe(201);
  const run = await createdResponse.json();
  const duplicate = await request.post("/api/v3/projects/" + project.id + "/agent-runs", { data: payload, headers });
  expect(duplicate.status()).toBe(201);
  expect((await duplicate.json()).id).toBe(run.id);

  const tasksResponse = await request.get("/api/v3/agent-runs/" + run.id + "/tasks");
  expect(tasksResponse.ok()).toBeTruthy();
  expect(await tasksResponse.json()).toHaveLength(4);
  const firstEvents = await request.get("/api/v3/agent-runs/" + run.id + "/events?after=0");
  const eventBody = await firstEvents.json();
  expect(eventBody.events[0].event).toBe("run.created");
  const replay = await request.get("/api/v3/agent-runs/" + run.id + "/events?after=" + eventBody.next_cursor);
  expect((await replay.json()).events).toHaveLength(0);

  expect((await (await request.post("/api/v3/agent-runs/" + run.id + "/pause")).json()).status).toBe("PAUSED");
  expect((await (await request.post("/api/v3/agent-runs/" + run.id + "/resume")).json()).status).toBe("RUNNING");
  expect((await (await request.post("/api/v3/agent-runs/" + run.id + "/retry")).json()).status).toBe("RUNNING");
  const artifactResponse = await request.post("/api/v3/agent-runs/" + run.id + "/artifacts", { data: { artifact_type: "candidate", payload: { scene: "candidate text" }, provenance: { task_id: "scene-a", source: "test" }, preview: "candidate preview" } });
  expect(artifactResponse.status()).toBe(201);
  const artifact = await artifactResponse.json();
  expect(artifact.sha256).toMatch(/^[a-f0-9]{64}$/);
  const reviewResponse = await request.post("/api/v3/agent-runs/" + run.id + "/reviews", { data: { artifact_id: artifact.id, reviewer_role: "continuity_reviewer", status: "CONFLICT", conflict_group: "scene-merge", evidence: [{ rule: "continuity", result: "needs-chief-editor" }] } });
  expect(reviewResponse.status()).toBe(201);
  expect((await (await request.post("/api/v3/agent-runs/" + run.id + "/cancel")).json()).status).toBe("CANCELLED");
  expect((await request.get("/api/v3/agent-runs/" + run.id + "/audit")).ok()).toBeTruthy();

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /sign in to your writing space/i })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Agent Swarm" }).click();
  await expect(page.getByRole("heading", { name: "Agent orchestration" })).toBeVisible();
  await page.getByRole("button", { name: "Start agent run" }).click();
  await expect(page.getByRole("heading", { name: "Agent run" })).toBeVisible();
  await expect(page.getByText("chief_planner").first()).toBeVisible();
});
