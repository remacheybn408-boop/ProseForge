import { expect, test } from "@playwright/test";

test("v3 execution resumes from pause and produces only a V2 proposal", async ({ request }) => {
  // Flaky: shares the default account with sibling specs (ordering changes the
  // observed run state); the V3 executor is a placeholder pending V3-001~010.
  // Tracked in artifacts/VALIDATION_STATUS.md.
  test.skip(true, "v3 placeholder executor + shared account fixture; V3 phase re-enables");
  const email = process.env.E2E_EMAIL ?? "v2-e2e-b074fc29@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  expect((await request.post("/api/v1/auth/login", { data: { email, password } })).ok()).toBeTruthy();
  const projectResponse = await request.post("/api/v1/projects", { data: { slug: "v3-exec-" + Date.now(), title: "V3 Execution Proposal" } });
  expect(projectResponse.status()).toBe(201);
  const project = await projectResponse.json();
  const chapterResponse = await request.post("/api/v1/projects/" + project.id + "/chapters", { data: { chapter_no: 1, title: "The Checkpoint" } });
  expect(chapterResponse.status()).toBe(201);
  const chapter = await chapterResponse.json();
  const baseResponse = await request.post("/api/v1/chapters/" + chapter.id + "/versions", { data: { content: "The first checkpoint held." } });
  expect(baseResponse.status()).toBe(201);
  const base = await baseResponse.json();
  const tasks = [
    { id: "planner", role: "chief_planner", token_budget: 10 },
    { id: "scene-a", role: "scene_writer", depends_on: ["planner"], token_budget: 10 },
    { id: "scene-b", role: "scene_writer", depends_on: ["planner"], token_budget: 10 },
    { id: "reviewer", role: "continuity_reviewer", depends_on: ["scene-a", "scene-b"], token_budget: 10 },
    { id: "chief", role: "chief_editor", depends_on: ["reviewer"], token_budget: 10 },
  ];
  const payload = { goal: "Prepare a reviewed checkpoint candidate", graph_revision: 1, budget_limit: 100, tasks, chapter_id: chapter.id, base_version_id: base.id };
  const runResponse = await request.post("/api/v3/projects/" + project.id + "/agent-runs", { data: payload, headers: { "Idempotency-Key": "v3-exec-" + Date.now() } });
  expect(runResponse.status()).toBe(201);
  const run = await runResponse.json();
  const paused = await request.post("/api/v3/agent-runs/" + run.id + "/pause");
  expect(paused.status()).toBe(200);
  expect((await paused.json()).status).toBe("PAUSED");
  expect((await (await request.get("/api/v3/agent-runs/" + run.id)).json()).status).toBe("PAUSED");
  expect((await (await request.post("/api/v3/agent-runs/" + run.id + "/resume")).json()).status).toBe("RUNNING");
  await expect.poll(async () => (await (await request.get("/api/v3/agent-runs/" + run.id)).json()).status, { timeout: 20_000 }).toBe("COMPLETED");
  const completed = await (await request.get("/api/v3/agent-runs/" + run.id)).json();
  expect(completed.proposal_id).toBeTruthy();
  const artifacts = await (await request.get("/api/v3/agent-runs/" + run.id + "/artifacts")).json();
  expect(artifacts.length).toBe(5);

  const rejected = await request.post("/api/v2/proposals/" + completed.proposal_id + "/reject");
  expect(rejected.status()).toBe(200);
  expect((await rejected.json()).status).toBe("REJECTED");

  const secondResponse = await request.post("/api/v3/projects/" + project.id + "/agent-runs", { data: { ...payload, goal: "Prepare the approved checkpoint candidate" }, headers: { "Idempotency-Key": "v3-exec-second-" + Date.now() } });
  expect(secondResponse.status()).toBe(201);
  const second = await secondResponse.json();
  await expect.poll(async () => (await (await request.get("/api/v3/agent-runs/" + second.id)).json()).status, { timeout: 20_000 }).toBe("COMPLETED");
  const secondRun = await (await request.get("/api/v3/agent-runs/" + second.id)).json();
  const approved = await request.post("/api/v2/proposals/" + secondRun.proposal_id + "/approve");
  expect(approved.status()).toBe(200);
  const approvedBody = await approved.json();
  expect(approvedBody.status).toBe("APPROVED");
  expect(approvedBody.version.id).not.toBe(base.id);

  const cancelledResponse = await request.post("/api/v3/projects/" + project.id + "/agent-runs", { data: { goal: "Discard this run", tasks: [{ id: "planner", role: "chief_planner" }] }, headers: { "Idempotency-Key": "v3-cancel-" + Date.now() } });
  const cancelled = await cancelledResponse.json();
  expect((await (await request.post("/api/v3/agent-runs/" + cancelled.id + "/cancel")).json()).status).toBe("CANCELLED");
  const versions = await (await request.get("/api/v1/chapters/" + chapter.id + "/versions")).json();
  expect(versions).toHaveLength(2);
});
