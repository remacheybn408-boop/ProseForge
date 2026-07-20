import { createHash } from "node:crypto";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

type Project = { id: string; title: string };
type Conversation = { id: string; branch_id: string };
type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: string;
  context_snapshot_id?: string | null;
  parent_message_id?: string | null;
};
type Branch = { id: string; name: string };
type Chapter = { id: string; active_version_id?: string | null };
type ChapterVersion = { id: string; version_no: number; content: string };
type Workflow = { id: string; status: string };
type ExportManifest = {
  id: string;
  project_id: string;
  format: string;
  template: string;
  title: string | null;
  locale: string;
  version_ids: string[];
  content_hashes: Record<string, string>;
  file_sha256: string;
  byte_size: number;
  download_url: string;
};
type HttpResponse = {
  status(): number;
  text(): Promise<string>;
  json(): Promise<unknown>;
  headers(): Record<string, string>;
};

const sha256 = (value: string | Buffer) => createHash("sha256").update(value).digest("hex");

async function json<T>(response: HttpResponse, expectedStatus = 200): Promise<T> {
  expect(response.status(), await response.text()).toBe(expectedStatus);
  return response.json() as Promise<T>;
}

async function messages(request: APIRequestContext, conversationId: string, branchId: string): Promise<Message[]> {
  return json<Message[]>(await request.get(`/api/v1/conversations/${conversationId}/branches/${branchId}/messages`));
}

async function waitForCompletedAssistant(request: APIRequestContext, conversationId: string, branchId: string): Promise<Message> {
  let completed: Message | undefined;
  await expect.poll(async () => {
    const branchMessages = await messages(request, conversationId, branchId);
    completed = [...branchMessages].reverse().find(item => item.role === "assistant" && item.status === "COMPLETED");
    return completed?.status;
  }, { timeout: 30_000, intervals: [250, 500, 1_000] }).toBe("COMPLETED");
  return completed!;
}

async function waitForWorkflowStatus(request: APIRequestContext, workflowId: string, status: string): Promise<Workflow> {
  let workflow: Workflow | undefined;
  await expect.poll(async () => {
    workflow = await json<Workflow>(await request.get(`/api/v1/workflows/${workflowId}`));
    return workflow.status;
  }, { timeout: 30_000, intervals: [200, 500, 1_000] }).toBe(status);
  return workflow!;
}

async function selectAllManuscript(page: Page): Promise<void> {
  const editor = page.getByTestId("tiptap-manuscript");
  await expect(editor).toBeVisible();
  // press() focuses the element without a mouse click: clicking first would place
  // a caret, and the async collapse event can race the select-all and unmount the
  // toolbar (observed: selection collapses to 0 while the editor stays focused).
  await editor.press("Control+A");
  await expect(page.getByLabel("Manuscript actions")).toBeVisible();
}

test.use({ trace: "off" }); // Manuscript text must not be retained in Playwright traces.

test("v2 professional flow completes the real ten-step workspace journey", async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  const email = process.env.E2E_EMAIL ?? "v2-e2e-b074fc29@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  const runId = `${Date.now()}-${testInfo.workerIndex}`;
  const requestIds = new Set<string>();
  const rememberRequestId = (response: HttpResponse) => {
    const id = response.headers()["x-request-id"] ?? response.headers()["x-trace-id"];
    if (id) requestIds.add(id);
  };
  // Pin the UI language so localized selectors (export dialog) stay deterministic.
  await page.addInitScript(() => { localStorage.setItem("proseforge.language", "en"); });

  const setup = await request.post("/api/v1/auth/setup", { data: { email, password } });
  expect([201, 409]).toContain(setup.status());
  const apiLogin = await request.post("/api/v1/auth/login", { data: { email, password } });
  expect(apiLogin.ok(), await apiLogin.text()).toBeTruthy();
  const credential = await request.post("/api/v1/credentials", {
    data: { provider: "openai", api_key: "mock-api-key", base_url: "http://provider-mock:8080/v1", allow_local: true },
  });
  expect([201, 409]).toContain(credential.status());

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /sign in to your writing space/i })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Projects", exact: true }).click();

  let project!: Project;
  await test.step("1. Create a project through the UI", async () => {
    await page.getByRole("button", { name: /new project/i }).click();
    await page.getByLabel("Project title").fill(`V2 Professional ${runId}`);
    await page.getByLabel("URL slug").fill(`v2-professional-${runId}`);
    const responsePromise = page.waitForResponse(response => response.url().endsWith("/api/v1/projects") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Create project" }).click();
    const response = await responsePromise;
    rememberRequestId(response);
    project = await json<Project>(response, 201);
    await expect(page).toHaveURL(new RegExp(`/projects/${project.id}/outline$`));
  });

  let conversation!: Conversation;
  let originalBranchId = "";
  let initialSend!: { user_message_id: string; assistant_message_id: string };
  const firstPrompt = "Check Mira's return to the harbor and keep the map continuity exact.";
  await test.step("2. Create a conversation and send a message through the UI", async () => {
    const conversationResponsePromise = page.waitForResponse(response => response.url().endsWith("/api/v1/conversations") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Companion chat" }).click();
    const conversationResponse = await conversationResponsePromise;
    rememberRequestId(conversationResponse);
    conversation = await json<Conversation>(conversationResponse);
    originalBranchId = conversation.branch_id;
    await expect(page).toHaveURL(new RegExp(`/chat/${conversation.id}/${originalBranchId}$`));

    await page.getByLabel("Message").fill(firstPrompt);
    const sendResponsePromise = page.waitForResponse(response => response.url().endsWith(`/api/v2/conversations/${conversation.id}/messages`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "Send" }).click();
    const sendResponse = await sendResponsePromise;
    rememberRequestId(sendResponse);
    initialSend = await json(sendResponse);
    await expect(page.locator('article[aria-label="user message"]')).toContainText(firstPrompt);
  });

  let initialAssistant!: Message;
  await test.step("3. Wait for persisted assistant completion and attributable usage", async () => {
    initialAssistant = await waitForCompletedAssistant(request, conversation.id, originalBranchId);
    expect(initialAssistant.id).toBe(initialSend.assistant_message_id);
    await expect(page.locator('article[aria-label="assistant message"]').filter({ hasText: initialAssistant.content })).toBeVisible();

    await expect.poll(async () => {
      const response = await request.get(`/api/v1/usage/records?conversation_id=${conversation.id}&message_id=${initialAssistant.id}`);
      const records = await json<Array<{ message_id: string; is_final: boolean; total_tokens: number }>>(response);
      return records.some(record => record.message_id === initialAssistant.id && record.is_final && record.total_tokens > 0);
    }, { timeout: 30_000, intervals: [250, 500, 1_000] }).toBeTruthy();
  });

  let editedBranchId = "";
  const editedPrompt = "Check Mira's return to the flooded harbor and preserve the map continuity.";
  await test.step("4. Edit an earlier user message into a new branch and preserve the old branch", async () => {
    const oldBranchBefore = await messages(request, conversation.id, originalBranchId);
    const userCard = page.locator('article[aria-label="user message"]').filter({ hasText: firstPrompt });
    await userCard.getByRole("button", { name: "Edit" }).click();
    await userCard.getByLabel("Edit message").fill(editedPrompt);
    const editResponsePromise = page.waitForResponse(response => response.url().includes(`/api/v2/conversations/${conversation.id}/messages/`) && response.url().endsWith("/edit") && response.request().method() === "POST");
    await userCard.getByRole("button", { name: "Save edit" }).click();
    const editResponse = await editResponsePromise;
    rememberRequestId(editResponse);
    const edited = await json<{ branch_id: string; replacement_message_id: string }>(editResponse);
    editedBranchId = edited.branch_id;
    expect(editedBranchId).not.toBe(originalBranchId);
    await expect(page).toHaveURL(new RegExp(`/chat/${conversation.id}/${editedBranchId}$`));
    await expect(page.getByText("Edit saved as a new branch.")).toBeVisible();

    expect(await messages(request, conversation.id, originalBranchId)).toEqual(oldBranchBefore);
    const editedMessages = await messages(request, conversation.id, editedBranchId);
    expect(editedMessages.some(item => item.id === edited.replacement_message_id && item.content === editedPrompt)).toBeTruthy();

    await page.getByRole("button", { name: "Compare" }).first().click();
    await expect(page.getByLabel("Branch comparison")).toBeVisible();
  });

  await test.step("5. Regenerate a reply and compare candidates in the UI", async () => {
    const branches = await json<Branch[]>(await request.get(`/api/v2/conversations/${conversation.id}/branches`));
    const originalBranch = branches.find(branch => branch.id === originalBranchId)!;
    await page.getByRole("button", { name: originalBranch.name, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${originalBranchId}$`));

    const assistantCard = page.locator('article[aria-label="assistant message"]').filter({ hasText: initialAssistant.content });
    const regenerateResponsePromise = page.waitForResponse(response => response.url().includes(`/api/v2/conversations/${conversation.id}/messages/`) && response.url().endsWith("/regenerate") && response.request().method() === "POST");
    await assistantCard.getByRole("button", { name: "Regenerate" }).click();
    const regenerateResponse = await regenerateResponsePromise;
    rememberRequestId(regenerateResponse);
    const regenerated = await json<{ message_id: string }>(regenerateResponse);

    await expect.poll(async () => {
      const tree = await json<Message[]>(await request.get(`/api/v2/conversations/${conversation.id}/branches/${originalBranchId}/tree`));
      return tree.find(item => item.id === regenerated.message_id)?.status;
    }, { timeout: 30_000, intervals: [250, 500, 1_000] }).toBe("COMPLETED");
    await expect(page.getByRole("button", { name: "Next candidate" })).toBeVisible();
    const candidateCounter = page.locator(".candidate-counter");
    await expect(candidateCounter).toContainText("/2");
    const before = await candidateCounter.textContent();
    await page.getByRole("button", { name: "Next candidate" }).click();
    await expect(candidateCounter).not.toHaveText(before ?? "");

    const refreshedBranches = await json<Branch[]>(await request.get(`/api/v2/conversations/${conversation.id}/branches`));
    const editedBranch = refreshedBranches.find(branch => branch.id === editedBranchId)!;
    await page.getByRole("button", { name: new RegExp(editedBranch.name) }).click();
  });

  let pinnedFactId = "";
  await test.step("6. Create and pin a Story Bible fact, then prove the next snapshot injects it", async () => {
    await page.getByRole("button", { name: "Story Bible" }).click();
    await page.getByRole("button", { name: "New fact" }).click();
    await page.getByLabel("Fact key").fill("Mira");
    await page.getByLabel("Triggers").fill("Mira, flooded harbor");
    await page.getByLabel("Summary").fill("Mira always carries the brass map home.");
    const createFactResponsePromise = page.waitForResponse(response => response.url().endsWith(`/api/v2/projects/${project.id}/story-bible/entries`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "Save fact" }).click();
    const createFactResponse = await createFactResponsePromise;
    rememberRequestId(createFactResponse);
    const fact = await json<{ id: string; pinned: boolean }>(createFactResponse, 201);
    pinnedFactId = fact.id;
    expect(fact.pinned).toBeFalsy();

    const factCard = page.locator("article.story-fact-card").filter({ hasText: "Mira" });
    const pinResponsePromise = page.waitForResponse(response => response.url().endsWith(`/api/v2/story-bible/${pinnedFactId}/pin`) && response.request().method() === "POST");
    await factCard.getByRole("button", { name: "Pin", exact: true }).click();
    const pinResponse = await pinResponsePromise;
    rememberRequestId(pinResponse);
    expect((await json<{ pinned: boolean }>(pinResponse)).pinned).toBeTruthy();
    await expect(factCard.getByText("PIN", { exact: true })).toBeVisible();

    await page.goBack();
    await expect(page).toHaveURL(new RegExp(`/chat/${conversation.id}/${editedBranchId}$`));
    await page.getByRole("textbox", { name: "Message" }).fill("Mira reaches the flooded harbor. Continue with the brass map fact intact.");
    const sendResponsePromise = page.waitForResponse(response => response.url().endsWith(`/api/v2/conversations/${conversation.id}/messages`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "Send" }).click();
    const sendResponse = await sendResponsePromise;
    rememberRequestId(sendResponse);
    await json(sendResponse);
    const assistant = await waitForCompletedAssistant(request, conversation.id, editedBranchId);
    expect(assistant.context_snapshot_id).toBeTruthy();
    const snapshot = await json<{ payload: { injected_fact_ids: string[] } }>(await request.get(`/api/v1/context/snapshots/${assistant.context_snapshot_id}`));
    expect(snapshot.payload.injected_fact_ids).toContain(pinnedFactId);
  });

  let chapter!: Chapter;
  let baseVersion!: ChapterVersion;
  const manuscript = "Mira unfolded the brass map. The flooded harbor reflected the dawn.";
  await test.step("7. Select manuscript text and request review and rewrite through the UI", async () => {
    chapter = await json<Chapter>(await request.post(`/api/v1/projects/${project.id}/chapters`, { data: { chapter_no: 1, title: "The Map Home" } }), 201);
    baseVersion = await json<ChapterVersion>(await request.post(`/api/v1/chapters/${chapter.id}/versions`, { data: { content: manuscript } }), 201);
    const versionsBefore = await json<ChapterVersion[]>(await request.get(`/api/v1/chapters/${chapter.id}/versions`));

    await page.getByRole("button", { name: "Writing Studio" }).click();
    await expect(page.getByRole("button", { name: /The Map Home/ })).toBeVisible();
    await expect(page.getByTestId("tiptap-manuscript")).toContainText("Mira unfolded the brass map");

    // The selection toolbar re-renders with ProseMirror's async selection sync, so a
    // click can race a toolbar unmount; retry each select+click unit until the
    // request is actually observed (duplicates are harmless here).
    let reviewResponse!: Awaited<ReturnType<Page["waitForResponse"]>>;
    await expect(async () => {
      await selectAllManuscript(page);
      const responsePromise = page.waitForResponse(response => response.url().endsWith(`/api/v2/chapters/${chapter.id}/selection-actions`) && response.request().method() === "POST", { timeout: 15_000 });
      await page.getByLabel("Manuscript actions").getByRole("button", { name: "review" }).click();
      reviewResponse = await responsePromise;
      expect(reviewResponse.status()).toBe(201);
    }).toPass({ timeout: 60_000, intervals: [500, 1_000] });
    rememberRequestId(reviewResponse);
    const review = await json<{ review_id: string }>(reviewResponse, 201);
    expect(review.review_id).toBeTruthy();
    await expect(page.getByText("Review report ready.")).toBeVisible();
    expect(await json<ChapterVersion[]>(await request.get(`/api/v1/chapters/${chapter.id}/versions`))).toEqual(versionsBefore);

    let rewriteResponse!: Awaited<ReturnType<Page["waitForResponse"]>>;
    await expect(async () => {
      await selectAllManuscript(page);
      const responsePromise = page.waitForResponse(response => response.url().endsWith(`/api/v2/chapters/${chapter.id}/selection-actions`) && response.request().method() === "POST", { timeout: 15_000 });
      await page.getByLabel("Manuscript actions").getByRole("button", { name: "rewrite" }).click();
      rewriteResponse = await responsePromise;
      expect(rewriteResponse.status()).toBe(201);
    }).toPass({ timeout: 60_000, intervals: [500, 1_000] });
    rememberRequestId(rewriteResponse);
    const rewrite = await json<{ proposal_id: string }>(rewriteResponse, 201);
    expect(rewrite.proposal_id).toBeTruthy();
    await expect(page.getByLabel("Proposal diff")).toBeVisible();
  });

  let approvedVersion!: ChapterVersion;
  await test.step("8. Accept selected diff hunks and assert an immutable new version", async () => {
    const diff = page.getByLabel("Proposal diff");
    const hunks = diff.getByRole("checkbox");
    expect(await hunks.count()).toBeGreaterThan(0);
    await expect(hunks.first()).toBeChecked();
    for (let index = 1; index < await hunks.count(); index += 1) await hunks.nth(index).uncheck();

    const approveResponsePromise = page.waitForResponse(response => /\/api\/v2\/(revision-)?proposals\/[^/]+\/approve$/.test(new URL(response.url()).pathname) && response.request().method() === "POST");
    await page.getByRole("button", { name: "Approve proposal (A)" }).click();
    const approveResponse = await approveResponsePromise;
    rememberRequestId(approveResponse);
    const approval = await json<{ status: string; version: ChapterVersion }>(approveResponse);
    expect(approval.status).toBe("VERSION_CREATED");
    approvedVersion = approval.version;
    expect(approvedVersion.id).not.toBe(baseVersion.id);
    await expect(page.getByText("Proposal approved as a new version.")).toBeVisible();

    const versions = await json<ChapterVersion[]>(await request.get(`/api/v1/chapters/${chapter.id}/versions`));
    expect(versions.map(version => version.id)).toEqual(expect.arrayContaining([baseVersion.id, approvedVersion.id]));
    expect(versions.filter(version => version.id === approvedVersion.id)).toHaveLength(1);
  });

  let workflow!: Workflow;
  await test.step("9. Start and control a workflow, then reload from its persisted snapshot", async () => {
    await page.getByRole("button", { name: "Outline intake" }).click();
    await page.getByLabel("Outline title").fill(`Recovery flow ${runId}`);
    await page.getByLabel("Outline or story notes").fill("A complete recovery test about Mira returning home with the map.");
    await page.getByRole("button", { name: "Import and analyze" }).click();
    await page.getByPlaceholder("Answer the missing requirement").fill("Mira, a determined cartographer");
    await page.getByRole("button", { name: "Save answer" }).click();
    const workflowResponsePromise = page.waitForResponse(response => response.url().endsWith(`/api/v1/projects/${project.id}/workflows/novel`) && response.request().method() === "POST");
    await page.getByRole("button", { name: /confirm and create workflow/i }).click();
    const workflowResponse = await workflowResponsePromise;
    rememberRequestId(workflowResponse);
    workflow = await json<Workflow>(workflowResponse, 201);
    await expect(page).toHaveURL(new RegExp(`/workflows/${workflow.id}$`));
    await waitForWorkflowStatus(request, workflow.id, "RUNNING");

    const pauseResponsePromise = page.waitForResponse(response => response.url().endsWith(`/api/v1/workflows/${workflow.id}/pause`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "暂停" }).click();
    const pauseResponse = await pauseResponsePromise;
    rememberRequestId(pauseResponse);
    expect((await json<Workflow>(pauseResponse)).status).toBe("PAUSED");

    await page.reload();
    await expect(page).toHaveURL(new RegExp(`/workflows/${workflow.id}$`));
    await expect(page.getByText(/PAUSED/).first()).toBeVisible();
    expect((await json<Workflow>(await request.get(`/api/v1/workflows/${workflow.id}`))).status).toBe("PAUSED");

    const resumeResponsePromise = page.waitForResponse(response => response.url().endsWith(`/api/v1/workflows/${workflow.id}/resume`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "继续" }).click();
    const resumeResponse = await resumeResponsePromise;
    rememberRequestId(resumeResponse);
    expect((await json<Workflow>(resumeResponse)).status).toBe("QUEUED");
    await waitForWorkflowStatus(request, workflow.id, "RUNNING");

    const retryResponsePromise = page.waitForResponse(response => response.url().endsWith(`/api/v1/workflows/${workflow.id}/retry`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "重试" }).click();
    const retryResponse = await retryResponsePromise;
    rememberRequestId(retryResponse);
    expect((await json<Workflow>(retryResponse)).status).toBe("RETRYING");
    await waitForWorkflowStatus(request, workflow.id, "RUNNING");

    const cancelResponsePromise = page.waitForResponse(response => response.url().endsWith(`/api/v1/workflows/${workflow.id}/cancel`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "取消" }).click();
    const cancelResponse = await cancelResponsePromise;
    rememberRequestId(cancelResponse);
    expect((await json<Workflow>(cancelResponse)).status).toBe("CANCELLED");
  });

  await test.step("10. Export Markdown, DOCX and EPUB and verify source manifests and hashes", async () => {
    await page.getByRole("button", { name: "Writing Studio" }).click();
    await page.getByRole("button", { name: /The Map Home/ }).click();
    await expect(page.getByText(/Loaded saved version \d+/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Export snapshot", exact: true })).toBeVisible();
    await page.evaluate(() => { window.open = () => null; });
    await page.getByRole("button", { name: "Export snapshot", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Export snapshot" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("checkbox")).toHaveCount(2);

    // The export accepts at most one version per chapter: pin only the approved version.
    for (const checkbox of await dialog.getByRole("checkbox").all()) await checkbox.uncheck();
    await dialog.locator("label", { hasText: approvedVersion.id }).getByRole("checkbox").check();

    const evidence: Record<string, { download_sha256: string; manifest: ExportManifest }> = {};
    for (const format of ["md", "docx", "epub"] as const) {
      await dialog.getByLabel("Export format").selectOption(format);
      await dialog.getByLabel("Export title").fill(`V2 verified ${runId}`);
      const exportResponsePromise = page.waitForResponse(response => response.url().endsWith(`/api/v1/projects/${project.id}/exports`) && response.request().method() === "POST");
      await dialog.getByRole("button", { name: "Generate export snapshot" }).click();
      const exportResponse = await exportResponsePromise;
      rememberRequestId(exportResponse);
      const manifest = await json<ExportManifest>(exportResponse, 201);
      expect(manifest.id).toBeTruthy();
      expect(manifest.project_id).toBe(project.id);
      expect(manifest.format).toBe(format);
      expect(manifest.template).toBe("archive");
      expect(manifest.title).toBe(`V2 verified ${runId}`);
      expect(manifest.version_ids).toEqual([approvedVersion.id]);
      expect(manifest.content_hashes[approvedVersion.id]).toBe(sha256(approvedVersion.content));
      expect(manifest.file_sha256).toMatch(/^[a-f0-9]{64}$/);
      expect(manifest.byte_size).toBeGreaterThan(0);
      expect(manifest.download_url).toBe(`/api/v1/projects/${project.id}/exports/${manifest.id}/download`);

      const persisted = await json<ExportManifest>(await request.get(`/api/v1/projects/${project.id}/exports/${manifest.id}`));
      expect(persisted).toEqual(manifest);

      const download = await request.get(manifest.download_url);
      expect(download.ok(), await download.text()).toBeTruthy();
      expect(download.headers()["x-proseforge-manifest-id"]).toBe(manifest.id);
      expect(download.headers()["x-proseforge-file-sha256"]).toBe(manifest.file_sha256);
      const bytes = await download.body();
      expect(bytes.byteLength).toBe(manifest.byte_size);
      expect(sha256(bytes)).toBe(manifest.file_sha256);
      if (format === "md") expect(bytes.toString("utf8")).toContain(approvedVersion.content);
      else expect(bytes.subarray(0, 2).toString("ascii")).toBe("PK");
      evidence[format] = { download_sha256: sha256(bytes), manifest };
    }
    await testInfo.attach("v2-export-evidence.json", { body: Buffer.from(JSON.stringify(evidence, null, 2)), contentType: "application/json" });
  });

  await testInfo.attach("v2-request-ids.json", {
    body: Buffer.from(JSON.stringify([...requestIds].sort(), null, 2)),
    contentType: "application/json",
  });
});
