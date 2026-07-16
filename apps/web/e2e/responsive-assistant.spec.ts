import { expect, test } from "@playwright/test";

test("responsive app shell serves a healthy page", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const response = await page.goto("/");
  expect(response?.ok()).toBeTruthy();
});

test("authenticated writing studio keeps the assistant visible on mobile", async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const email = process.env.E2E_EMAIL ?? "e2e@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  await request.post("/api/v1/auth/setup", { data: { email, password } });

  await page.goto("/");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码").fill(password);
  await page.locator(".auth-card button.primary").click();
  await expect(page.getByRole("button", { name: "English", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "English", exact: true }).click();

  const projectResponse = await page.request.post("/api/v1/projects", {
    data: { slug: `responsive-e2e-${Date.now()}`, title: "Responsive E2E project" },
  });
  expect(projectResponse.ok()).toBeTruthy();
  const project = await projectResponse.json() as { id: string };
  await page.evaluate(id => window.localStorage.setItem("proseforge.current-project", id), project.id);
  await page.goto(`/projects/${project.id}/studio`);

  await expect(page.locator(".review-pane")).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.locator(".chat-composer textarea")).toBeVisible();
  await page.getByRole("button", { name: "Collapse assistant" }).click();
  await expect(page.getByRole("button", { name: "Expand assistant" })).toBeVisible();
  await expect(page.getByText("Writing companion", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Expand assistant" }).click();
  await expect(page.locator(".chat-composer textarea")).toBeVisible();
});
