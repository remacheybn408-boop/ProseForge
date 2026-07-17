import { expect, test } from "@playwright/test";

test("v3 concurrent controls retain a unique audit cursor", async ({ request }) => {
  const email = process.env.E2E_EMAIL ?? "v2-e2e-b074fc29@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  expect((await request.post("/api/v1/auth/login", { data: { email, password } })).ok()).toBeTruthy();
  const projectResponse = await request.post("/api/v1/projects", { data: { slug: "v3-concurrency-" + Date.now(), title: "V3 Concurrency Fault" } });
  const project = await projectResponse.json();
  const created = await request.post("/api/v3/projects/" + project.id + "/agent-runs", { data: { goal: "serialize controls", tasks: [{ id: "planner", role: "chief_planner" }] }, headers: { "Idempotency-Key": "v3-concurrency-" + Date.now() } });
  const run = await created.json();
  const responses = await Promise.all([
    request.post("/api/v3/agent-runs/" + run.id + "/pause"),
    request.post("/api/v3/agent-runs/" + run.id + "/resume"),
    request.post("/api/v3/agent-runs/" + run.id + "/pause"),
  ]);
  expect(responses.every(response => [200, 409].includes(response.status()))).toBeTruthy();
  const audit = await (await request.get("/api/v3/agent-runs/" + run.id + "/audit")).json();
  const sequences = audit.map((event: { sequence: number }) => event.sequence);
  expect(new Set(sequences).size).toBe(sequences.length);
});
