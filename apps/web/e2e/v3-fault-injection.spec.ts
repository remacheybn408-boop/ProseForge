import { expect, test } from "@playwright/test";

test("v3 deterministic fault modes terminate durably and redact no raw prompt", async ({ request }) => {
  const email = process.env.E2E_EMAIL ?? "v2-e2e-b074fc29@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  expect((await request.post("/api/v1/auth/login", { data: { email, password } })).ok()).toBeTruthy();
  const projectResponse = await request.post("/api/v1/projects", { data: { slug: "v3-faults-" + Date.now(), title: "V3 Fault Injection" } });
  const project = await projectResponse.json();
  for (const mode of ["provider_timeout", "malformed_json", "budget_exhaustion"] as const) {
    const created = await request.post("/api/v3/projects/" + project.id + "/agent-runs", {
      data: { goal: "fault test " + mode, fault_mode: mode, tasks: [{ id: "planner", role: "chief_planner", token_budget: 1 }], budget_limit: 1 },
      headers: { "Idempotency-Key": "v3-fault-" + mode + "-" + Date.now() },
    });
    expect(created.status()).toBe(201);
    const run = await created.json();
    await expect.poll(async () => (await (await request.get("/api/v3/agent-runs/" + run.id)).json()).status, { timeout: 15_000 }).toBe(mode === "budget_exhaustion" ? "BUDGET_EXHAUSTED" : "FAILED");
    const state = await (await request.get("/api/v3/agent-runs/" + run.id)).json();
    expect(state.terminal_reason).not.toContain("E2ePassw0rd");
    const audit = await (await request.get("/api/v3/agent-runs/" + run.id + "/audit")).json();
    expect(audit.some((event: { event: string }) => event.event === (mode === "budget_exhaustion" ? "run.budget_exhausted" : "run.failed"))).toBeTruthy();
  }
});

test("v3 worker crash after artifact commit is replay-safe", async ({ request }) => {
  const email = process.env.E2E_EMAIL ?? "v2-e2e-b074fc29@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  expect((await request.post("/api/v1/auth/login", { data: { email, password } })).ok()).toBeTruthy();
  const projectResponse = await request.post("/api/v1/projects", { data: { slug: "v3-crash-" + Date.now(), title: "V3 Crash Replay" } });
  expect(projectResponse.status()).toBe(201);
  const project = await projectResponse.json();
  const runResponse = await request.post(`/api/v3/projects/${project.id}/agent-runs`, {
    data: {
      goal: "Replay one committed candidate",
      graph_revision: 1,
      budget_limit: 10,
      fault_mode: "crash_after_artifact_commit",
      tasks: [{ id: "planner", role: "chief_planner", token_budget: 1 }],
    },
    headers: { "Idempotency-Key": "v3-crash-" + Date.now() },
  });
  expect(runResponse.status()).toBe(201);
  const run = await runResponse.json();
  await expect.poll(async () => (await (await request.get(`/api/v3/agent-runs/${run.id}`)).json()).status, { timeout: 30_000 }).toBe("COMPLETED");
  const artifacts = await (await request.get(`/api/v3/agent-runs/${run.id}/artifacts`)).json();
  expect(artifacts).toHaveLength(1);
  const tasks = await (await request.get(`/api/v3/agent-runs/${run.id}/tasks`)).json();
  expect(tasks).toEqual([expect.objectContaining({ status: "SUCCEEDED", attempts: 1 })]);
  const events = (await (await request.get(`/api/v3/agent-runs/${run.id}/events`)).json()).events;
  expect(events.filter((event: { event: string }) => event.event === "artifact.committed")).toHaveLength(1);
  expect(events.some((event: { event: string }) => event.event === "run.completed")).toBeTruthy();
});
