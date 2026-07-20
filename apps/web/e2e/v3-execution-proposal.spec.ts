import { createHash } from "node:crypto";
import { expect, test, type APIRequestContext } from "@playwright/test";

test.use({ trace: "off" }); // Manuscript text must not be retained in Playwright traces.

const sha256 = (value: string | Buffer) => createHash("sha256").update(value).digest("hex");

// The product allows exactly one account (/api/v1/auth/setup is one-shot), so this
// spec shares the suite account. Run creation can collide with sibling specs'
// in-flight runs against the per-user active-run cap (MAX_ACTIVE_RUNS_PER_USER=3
// in agent_runs.py); retry only that specific 409 with the same idempotency key.
async function createAgentRun(request: APIRequestContext, projectId: string, data: Record<string, unknown>, idempotencyKey: string) {
  let response = await request.post("/api/v3/projects/" + projectId + "/agent-runs", { data, headers: { "Idempotency-Key": idempotencyKey } });
  for (let attempt = 0; attempt < 3 && response.status() === 409; attempt += 1) {
    const body = await response.json();
    if (body?.error?.code !== "RUN_CONCURRENCY_LIMIT") return response;
    await new Promise(resolve => setTimeout(resolve, 1500));
    response = await request.post("/api/v3/projects/" + projectId + "/agent-runs", { data, headers: { "Idempotency-Key": idempotencyKey } });
  }
  return response;
}

test("v3 execution resumes from pause and produces only a V2 proposal", async ({ request }) => {
  test.setTimeout(120_000);
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
  const projectResponse = await request.post("/api/v1/projects", { data: { slug: "v3-exec-" + stamp, title: "V3 Execution Proposal" } });
  expect(projectResponse.status()).toBe(201);
  const project = await projectResponse.json();
  const chapterResponse = await request.post("/api/v1/projects/" + project.id + "/chapters", { data: { chapter_no: 1, title: "The Checkpoint" } });
  expect(chapterResponse.status()).toBe(201);
  const chapter = await chapterResponse.json();
  const baseResponse = await request.post("/api/v1/chapters/" + chapter.id + "/versions", { data: { content: "The first checkpoint held." } });
  expect(baseResponse.status()).toBe(201);
  const base = await baseResponse.json();
  expect(await (await request.get("/api/v1/chapters/" + chapter.id + "/versions")).json()).toHaveLength(1);

  const tasks = [
    { id: "planner", role: "chief_planner", token_budget: 10 },
    { id: "scene-a", role: "scene_writer", depends_on: ["planner"], token_budget: 10 },
    { id: "scene-b", role: "scene_writer", depends_on: ["planner"], token_budget: 10 },
    { id: "reviewer", role: "continuity_reviewer", depends_on: ["scene-a", "scene-b"], token_budget: 10 },
    { id: "chief", role: "chief_editor", depends_on: ["reviewer"], token_budget: 10 },
  ];
  // 5 mock role calls settle ~60 actual tokens; budget_limit stays well above.
  const payload = { goal: "Prepare a reviewed checkpoint candidate", graph_revision: 1, budget_limit: 1000, tasks, chapter_id: chapter.id, base_version_id: base.id };
  const runResponse = await createAgentRun(request, project.id, payload, "v3-exec-" + stamp);
  expect(runResponse.status(), await runResponse.text()).toBe(201);
  const run = await runResponse.json();

  // Pause immediately after create (from PENDING, before the worker drains the
  // mock-backed graph); the pause must persist across a fresh GET.
  const paused = await request.post("/api/v3/agent-runs/" + run.id + "/pause");
  expect(paused.status(), await paused.text()).toBe(200);
  expect((await paused.json()).status).toBe("PAUSED");
  expect((await (await request.get("/api/v3/agent-runs/" + run.id)).json()).status).toBe("PAUSED");
  // Quiescence window: let the create-enqueued worker observe PAUSED and back out
  // before resume re-enqueues, so two executor instances never overlap in flight
  // (an overlap could re-execute a claimed task and duplicate an artifact).
  await new Promise(resolve => setTimeout(resolve, 1500));
  expect((await (await request.post("/api/v3/agent-runs/" + run.id + "/resume")).json()).status).toBe("RUNNING");
  await expect.poll(async () => (await (await request.get("/api/v3/agent-runs/" + run.id)).json()).status, { timeout: 20_000 }).toBe("COMPLETED");
  const completed = await (await request.get("/api/v3/agent-runs/" + run.id)).json();
  expect(completed.proposal_id).toBeTruthy();

  // Blueprint step 3: one artifact per executed task — planner/scene candidates,
  // the reviewer's report, and the chief's merge candidate.
  const artifacts = await (await request.get("/api/v3/agent-runs/" + run.id + "/artifacts")).json();
  expect(artifacts).toHaveLength(5);
  expect(artifacts.filter((entry: { artifact_type: string }) => entry.artifact_type === "candidate")).toHaveLength(4);
  expect(artifacts.filter((entry: { artifact_type: string }) => entry.artifact_type === "report")).toHaveLength(1);
  // Mock reviewers emit one PASS/WARNING row per upstream artifact and never a
  // cross-reviewer conflict, so the proposal guard stays clear.
  const reviews = await (await request.get("/api/v3/agent-runs/" + run.id + "/reviews")).json();
  expect(reviews).toHaveLength(3);
  expect(reviews.every((entry: { status: string; conflict_group: string | null }) => ["PASS", "WARNING"].includes(entry.status) && !entry.conflict_group)).toBeTruthy();

  // Blueprint step 7: the chief-proposal endpoint replays the run's existing proposal.
  const chiefProposal = await request.post("/api/v3/agent-runs/" + run.id + "/chief-proposal");
  expect(chiefProposal.status(), await chiefProposal.text()).toBe(200);
  const chiefProposalBody = await chiefProposal.json();
  expect(chiefProposalBody.proposal_id).toBe(completed.proposal_id);
  expect(chiefProposalBody.guard_status).toBe("clear");

  // Blueprint step 8: reject the proposal, then rerun the swarm for a fresh one.
  const rejected = await request.post("/api/v2/proposals/" + completed.proposal_id + "/reject");
  expect(rejected.status()).toBe(200);
  expect((await rejected.json()).status).toBe("REJECTED");

  const secondResponse = await createAgentRun(request, project.id, { ...payload, goal: "Prepare the approved checkpoint candidate" }, "v3-exec-second-" + stamp);
  expect(secondResponse.status(), await secondResponse.text()).toBe(201);
  const second = await secondResponse.json();
  await expect.poll(async () => (await (await request.get("/api/v3/agent-runs/" + second.id)).json()).status, { timeout: 20_000 }).toBe("COMPLETED");
  const secondRun = await (await request.get("/api/v3/agent-runs/" + second.id)).json();
  expect(secondRun.proposal_id).toBeTruthy();
  expect(secondRun.proposal_id).not.toBe(completed.proposal_id);

  // Blueprint step 9: approving the V2 proposal writes exactly one new ChapterVersion.
  const approved = await request.post("/api/v2/proposals/" + secondRun.proposal_id + "/approve");
  expect(approved.status(), await approved.text()).toBe(200);
  const approvedBody = await approved.json();
  expect(approvedBody.status).toBe("VERSION_CREATED");
  expect(approvedBody.version.id).not.toBe(base.id);
  // The mock chief branch appended its deterministic merge appendix to the base text.
  expect(approvedBody.version.content).toBe("The first checkpoint held.\n\nMock chief merge appendix.");
  const versionsAfterApprove = await (await request.get("/api/v1/chapters/" + chapter.id + "/versions")).json();
  expect(versionsAfterApprove).toHaveLength(2);
  expect(versionsAfterApprove.map((version: { id: string }) => version.id)).toEqual(expect.arrayContaining([base.id, approvedBody.version.id]));

  // Blueprint step 11: export the approved version and verify the source hash chain.
  const exportResponse = await request.post("/api/v1/projects/" + project.id + "/exports", {
    data: { format: "md", version_ids: [approvedBody.version.id], title: "V3 verified " + stamp, template: "archive", locale: "en" },
  });
  expect(exportResponse.status(), await exportResponse.text()).toBe(201);
  const manifest = await exportResponse.json();
  expect(manifest.version_ids).toEqual([approvedBody.version.id]);
  expect(manifest.content_hashes[approvedBody.version.id]).toBe(sha256(approvedBody.version.content));
  expect(manifest.file_sha256).toMatch(/^[a-f0-9]{64}$/);
  expect(manifest.download_url).toBe("/api/v1/projects/" + project.id + "/exports/" + manifest.id + "/download");
  const persisted = await (await request.get("/api/v1/projects/" + project.id + "/exports/" + manifest.id)).json();
  expect(persisted).toEqual(manifest);
  const download = await request.get(manifest.download_url);
  expect(download.ok(), await download.text()).toBeTruthy();
  expect(download.headers()["x-proseforge-manifest-id"]).toBe(manifest.id);
  expect(download.headers()["x-proseforge-file-sha256"]).toBe(manifest.file_sha256);
  const bytes = await download.body();
  expect(bytes.byteLength).toBe(manifest.byte_size);
  expect(sha256(bytes)).toBe(manifest.file_sha256);
  expect(bytes.toString("utf8")).toContain(approvedBody.version.content);

  // Blueprint step 10: a cancelled run writes no proposal and no chapter version.
  const cancelledResponse = await createAgentRun(request, project.id, { goal: "Discard this run", tasks: [{ id: "planner", role: "chief_planner" }] }, "v3-cancel-" + stamp);
  expect(cancelledResponse.status(), await cancelledResponse.text()).toBe(201);
  const cancelled = await cancelledResponse.json();
  const cancelledControl = await request.post("/api/v3/agent-runs/" + cancelled.id + "/cancel");
  expect(cancelledControl.status(), await cancelledControl.text()).toBe(200);
  expect((await cancelledControl.json()).status).toBe("CANCELLED");
  expect(await (await request.get("/api/v1/chapters/" + chapter.id + "/versions")).json()).toHaveLength(2);
});
