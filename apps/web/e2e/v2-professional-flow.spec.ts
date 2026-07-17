import { createHash } from "node:crypto";
import { expect, test } from "@playwright/test";

test("v2 professional flow persists proposals, assistant usage and export snapshots", async ({ page, request }) => {
  const email = process.env.E2E_EMAIL ?? "v2-e2e-b074fc29@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  const setup = await request.post("/api/v1/auth/setup", { data: { email, password } });
  expect([201, 409]).toContain(setup.status());
  const login = await request.post("/api/v1/auth/login", { data: { email, password } });
  expect(login.ok()).toBeTruthy();

  const projectResponse = await request.post("/api/v1/projects", {
    data: { slug: `v2-professional-${Date.now()}`, title: "V2 Professional Flow" },
  });
  expect(projectResponse.status()).toBe(201);
  const project = await projectResponse.json();

  const credential = await request.post("/api/v1/credentials", {
    data: { provider: "openai", api_key: "mock-api-key", base_url: "http://provider-mock:8080/v1", allow_local: true },
  });
  expect([201, 409]).toContain(credential.status());

  const chapterResponse = await request.post(`/api/v1/projects/${project.id}/chapters`, {
    data: { chapter_no: 1, title: "The Map Home" },
  });
  expect(chapterResponse.status()).toBe(201);
  const chapter = await chapterResponse.json();
  const versionResponse = await request.post(`/api/v1/chapters/${chapter.id}/versions`, {
    data: { content: "Mira unfolded the map and chose the road home." },
  });
  expect(versionResponse.status()).toBe(201);
  const version = await versionResponse.json();

  const conversationResponse = await request.post("/api/v1/conversations", { data: { project_id: project.id, title: "Companion" } });
  expect(conversationResponse.ok()).toBeTruthy();
  const conversation = await conversationResponse.json();
  const messageResponse = await request.post(`/api/v1/conversations/${conversation.id}/messages`, {
    data: { branch_id: conversation.branch_id, content: "Check this chapter for continuity.", client_request_id: `v2-${Date.now()}`, provider: "openai", model: "gpt-4.1-mini" },
  });
  expect(messageResponse.ok()).toBeTruthy();
  await expect.poll(async () => {
    const response = await request.get(`/api/v1/conversations/${conversation.id}/branches/${conversation.branch_id}/messages`);
    const messages = await response.json();
    return messages.find((item: { role: string; status: string }) => item.role === "assistant")?.status ?? "PENDING";
  }, { timeout: 15_000 }).toBe("COMPLETED");

  const proposalResponse = await request.post(`/api/v2/chapters/${chapter.id}/proposals`, {
    data: { base_version_id: version.id, after_text: "Mira folded the map and chose the road home.", rationale: "Tighten the opening action." },
  });
  expect(proposalResponse.status()).toBe(201);
  const proposal = await proposalResponse.json();
  const approvalResponse = await request.post(`/api/v2/proposals/${proposal.id}/approve`);
  expect(approvalResponse.status()).toBe(200);
  const approval = await approvalResponse.json();
  expect(approval.status).toBe("APPROVED");
  expect(approval.version.id).not.toBe(version.id);

  const exportRequest = await request.post(`/api/v1/projects/${project.id}/exports`, {
    data: { format: "md", version_ids: [approval.version.id], title: "V2 Export", author: "ProseForge" },
  });
  expect(exportRequest.status()).toBe(202);
  const exportPlan = await exportRequest.json();
  const download = await request.get(exportPlan.download_url);
  expect(download.ok()).toBeTruthy();
  const bytes = await download.body();
  expect(createHash("sha256").update(bytes).digest("hex")).toHaveLength(64);
  const manifest = JSON.parse(download.headers()["x-proseforge-manifest"] ?? "{}");
  expect(manifest.version_ids).toContain(approval.version.id);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /sign in to your writing space/i })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Projects", exact: true }).click();
  await expect(page.locator("h2", { hasText: "Projects" })).toBeVisible();
  await expect(page.getByText("V2 Professional Flow").first()).toBeVisible();
});
