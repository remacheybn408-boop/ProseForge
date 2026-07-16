import { expect, test } from "@playwright/test";

test("workflow controls are protected until a session is established", async ({ request }) => {
  const response = await request.post("/api/v1/workflows/example/retry");
  expect(response.status()).toBe(401);
});

test("authenticated user can inspect a failed workflow and requeue a retry", async ({ page, request }) => {
  const email = process.env.E2E_EMAIL ?? "e2e@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  await request.post("/api/v1/auth/setup", { data: { email, password } });

  await page.goto("/");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.locator(".auth-card button.primary").click();
  await expect(page.getByRole("button", { name: "English", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "English", exact: true }).click();

  const slug = `workflow-e2e-${Date.now()}`;
  const projectResponse = await page.request.post("/api/v1/projects", { data: { slug, title: "Workflow controls E2E" } });
  expect(projectResponse.ok()).toBeTruthy();
  const project = await projectResponse.json() as { id: string };
  const outlineResponse = await page.request.post(`/api/v1/projects/${project.id}/outlines/import`, {
    data: {
      title: "Workflow controls outline",
      content: "A short adventure about Mira returning home.",
      data: { genre: "adventure", characters: ["Mira"], point_of_view: "third person", planned_chapters: 1, chapter_word_target: 1000 },
    },
  });
  expect(outlineResponse.ok()).toBeTruthy();
  const outline = await outlineResponse.json() as { id: string };
  const confirmationResponse = await page.request.post(`/api/v1/outlines/${outline.id}/confirm`);
  expect(confirmationResponse.ok()).toBeTruthy();
  const workflowResponse = await page.request.post(`/api/v1/projects/${project.id}/workflows/novel`, {
    data: { chapter_numbers: [1], provider: "provider-without-a-credential", model: "test-model" },
  });
  expect(workflowResponse.ok()).toBeTruthy();
  const workflow = await workflowResponse.json() as { id: string };

  const status = async () => (await page.request.get(`/api/v1/workflows/${workflow.id}`)).json().then((value: { status: string }) => value.status);
  await expect.poll(status, { timeout: 15_000 }).toBe("FAILED");
  await page.evaluate(id => window.localStorage.setItem("proseforge.current-workflow", id), workflow.id);
  await page.goto(`/projects/${project.id}/workflow`);
  await expect(page.getByRole("heading", { name: "Chapter workflow" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Pause" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Cancel" })).toBeDisabled();

  const retryResponse = page.waitForResponse(response => response.url().endsWith(`/api/v1/workflows/${workflow.id}/retry`) && response.request().method() === "POST");
  await page.getByRole("button", { name: "Retry" }).click();
  expect((await retryResponse).status()).toBe(200);
});
