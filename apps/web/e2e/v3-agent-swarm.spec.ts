import { expect, test, type APIRequestContext } from "@playwright/test";

test.use({ trace: "off" }); // Manuscript text must not be retained in Playwright traces.

// The product allows exactly one account (/api/v1/auth/setup is one-shot), so this
// spec shares the suite account. Cross-spec interference is neutralized instead by
// unique idempotency keys, unique project slugs, and pausing runs out of the active
// set quickly (PAUSED does not count against the per-user active-run cap).
async function createAgentRun(request: APIRequestContext, projectId: string, data: Record<string, unknown>, idempotencyKey: string) {
  // A 409 here can only be RUN_CONCURRENCY_LIMIT (sibling specs' in-flight runs
  // share the same per-user cap of 3); those windows are sub-second, so bounded
  // retries with the same idempotency key are safe and still replay-correct.
  let response = await request.post("/api/v3/projects/" + projectId + "/agent-runs", { data, headers: { "Idempotency-Key": idempotencyKey } });
  for (let attempt = 0; attempt < 3 && response.status() === 409; attempt += 1) {
    const body = await response.json();
    if (body?.error?.code !== "RUN_CONCURRENCY_LIMIT") return response;
    await new Promise(resolve => setTimeout(resolve, 1500));
    response = await request.post("/api/v3/projects/" + projectId + "/agent-runs", { data, headers: { "Idempotency-Key": idempotencyKey } });
  }
  return response;
}

test("v3 agent swarm is idempotent, replayable, reviewable, and visible in the workspace", async ({ page, request }) => {
  // Budget covers the long API phase (shared, rate-limited account) plus the UI
  // phase; sibling v3 specs running in parallel can stretch both.
  test.setTimeout(180_000);
  const email = process.env.E2E_EMAIL ?? "v2-e2e-b074fc29@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  const setup = await request.post("/api/v1/auth/setup", { data: { email, password } });
  expect([201, 409]).toContain(setup.status());
  expect((await request.post("/api/v1/auth/login", { data: { email, password } })).ok()).toBeTruthy();
  const credential = await request.post("/api/v1/credentials", {
    data: { provider: "openai", api_key: "mock-api-key", base_url: "http://provider-mock:8080/v1", allow_local: true },
  });
  expect([201, 409]).toContain(credential.status());

  const stamp = Date.now();
  const projectResponse = await request.post("/api/v1/projects", { data: { slug: "v3-agent-" + stamp, title: "V3 Agent Swarm" } });
  expect(projectResponse.status()).toBe(201);
  const project = await projectResponse.json();
  const graph = [
    { id: "planner", role: "chief_planner", token_budget: 10 },
    { id: "scene-a", role: "scene_writer", depends_on: ["planner"], token_budget: 10 },
    { id: "scene-b", role: "scene_writer", depends_on: ["planner"], token_budget: 10 },
    { id: "reviewer", role: "continuity_reviewer", depends_on: ["scene-a", "scene-b"], token_budget: 10 },
  ];
  // budget_limit stays generous: mock role calls settle 12 tokens each, and the
  // retry-driven re-executions below settle additional actual usage.
  const payload = { goal: "Draft and review two scenes", graph_revision: 1, budget_limit: 1000, tasks: graph };
  const idempotencyKey = "v3-e2e-" + stamp;
  const createdResponse = await createAgentRun(request, project.id, payload, idempotencyKey);
  expect(createdResponse.status(), await createdResponse.text()).toBe(201);
  const run = await createdResponse.json();
  const duplicate = await createAgentRun(request, project.id, payload, idempotencyKey);
  expect(duplicate.status()).toBe(201);
  expect((await duplicate.json()).id).toBe(run.id);

  // Pause immediately after create — from PENDING, before the worker drains the
  // mock-backed graph. A paused run has no event writers, so the cursor replay
  // below is deterministic; pause accepts PENDING or RUNNING either way.
  const pausedResponse = await request.post("/api/v3/agent-runs/" + run.id + "/pause");
  expect(pausedResponse.status(), await pausedResponse.text()).toBe(200);
  expect((await pausedResponse.json()).status).toBe("PAUSED");
  expect((await (await request.get("/api/v3/agent-runs/" + run.id)).json()).status).toBe("PAUSED");

  const tasksResponse = await request.get("/api/v3/agent-runs/" + run.id + "/tasks");
  expect(tasksResponse.ok()).toBeTruthy();
  const tasks = await tasksResponse.json();
  expect(tasks).toHaveLength(4);
  const firstEvents = await request.get("/api/v3/agent-runs/" + run.id + "/events?after=0");
  const eventBody = await firstEvents.json();
  expect(eventBody.events[0].event).toBe("run.created");
  const replay = await request.get("/api/v3/agent-runs/" + run.id + "/events?after=" + eventBody.next_cursor);
  expect((await replay.json()).events).toHaveLength(0);

  expect((await (await request.post("/api/v3/agent-runs/" + run.id + "/resume")).json()).status).toBe("RUNNING");
  expect((await (await request.post("/api/v3/agent-runs/" + run.id + "/retry")).json()).status).toBe("RUNNING");
  // Blueprint step 6: per-task retry re-queues a single task row; run stays RUNNING.
  const taskRetry = await request.post("/api/v3/agent-runs/" + run.id + "/retry?task_id=" + tasks[0].id);
  expect(taskRetry.status(), await taskRetry.text()).toBe(200);
  expect((await taskRetry.json()).status).toBe("RUNNING");

  const artifactResponse = await request.post("/api/v3/agent-runs/" + run.id + "/artifacts", { data: { artifact_type: "candidate", payload: { scene: "candidate text" }, provenance: { task_id: "scene-a", source: "test" }, preview: "candidate preview" } });
  expect(artifactResponse.status()).toBe(201);
  const artifact = await artifactResponse.json();
  expect(artifact.sha256).toMatch(/^[a-f0-9]{64}$/);
  const reviewResponse = await request.post("/api/v3/agent-runs/" + run.id + "/reviews", { data: { artifact_id: artifact.id, reviewer_role: "continuity_reviewer", status: "CONFLICT", conflict_group: "scene-merge", evidence: [{ rule: "continuity", result: "needs-chief-editor" }] } });
  expect(reviewResponse.status(), await reviewResponse.text()).toBe(201);
  const reviews = await (await request.get("/api/v3/agent-runs/" + run.id + "/reviews")).json();
  expect(reviews.some((entry: { status: string; conflict_group: string | null }) => entry.status === "CONFLICT" && entry.conflict_group === "scene-merge")).toBeTruthy();

  expect((await (await request.post("/api/v3/agent-runs/" + run.id + "/cancel")).json()).status).toBe("CANCELLED");
  expect((await request.get("/api/v3/agent-runs/" + run.id + "/audit")).ok()).toBeTruthy();

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /sign in to your writing space/i })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  // Wait for the signed-in shell before navigating, otherwise goto can race the
  // sign-in request and the studio route loads without a session.
  await expect(page.getByRole("button", { name: "Projects", exact: true })).toBeVisible({ timeout: 30_000 });
  await page.goto("/projects/" + project.id + "/studio");
  await page.getByRole("button", { name: "Agent Swarm" }).click();
  await expect(page.getByRole("heading", { name: "Agent orchestration" })).toBeVisible();
  // Run creation shares the per-user active-run cap with sibling specs; a 409
  // surfaces as "Could not start the agent run." and the button stays, so retry.
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await page.getByRole("button", { name: "Start agent run" }).click();
    try {
      await expect(page.getByRole("heading", { name: "Agent run" })).toBeVisible({ timeout: 8_000 });
      break;
    } catch { /* transient RUN_CONCURRENCY_LIMIT from the shared account */ }
  }
  await expect(page.getByRole("heading", { name: "Agent run" })).toBeVisible();
  await expect(page.getByText("chief_planner").first()).toBeVisible();
});
