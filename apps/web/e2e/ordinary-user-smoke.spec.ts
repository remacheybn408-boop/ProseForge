import { expect, test } from "@playwright/test";

test("ordinary user can use the Docker-backed writing workspace", async ({ page, request }) => {
  const email = process.env.E2E_EMAIL ?? "e2e@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  await request.post("/api/v1/auth/setup", { data: { email, password } });
  const health = await request.get("/api/v1/health/live");
  expect(health.ok()).toBeTruthy();
  await expect(health.json()).resolves.toEqual({ status: "ok" });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /sign in to your writing space/i })).toBeVisible();
  await expect(page.getByLabel("Email")).toHaveAttribute("type", "email");
  await expect(page.getByLabel("Password")).toHaveAttribute("type", "password");

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("h2", { hasText: "Projects" })).toBeVisible();

  await page.getByRole("button", { name: /new project/i }).click();
  await page.getByLabel("Project title").fill(`E2E Project ${Date.now()}`);
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByRole("heading", { name: /start from your story idea/i })).toBeVisible();
  await page.getByLabel("Outline title").fill("E2E Outline");
  await page.getByLabel("Outline or story notes").fill("A complete story about a cartographer who returns home and chooses hope.");
  await page.getByRole("button", { name: "Import and analyze" }).click();
  await expect(page.getByPlaceholder("Answer the missing requirement")).toBeVisible();
  await page.getByPlaceholder("Answer the missing requirement").fill("Mira, a determined cartographer");
  await page.getByRole("button", { name: "Save answer" }).click();
  await page.getByRole("button", { name: /confirm and create workflow/i }).click();
  await expect(page.getByRole("heading", { name: "Chapter workflow" })).toBeVisible();
  await page.getByRole("button", { name: "Writing Studio" }).click();
  await expect(page.getByRole("button", { name: /Chapter 1/i })).toBeVisible();
  await page.getByRole("textbox", { name: "" }).first().fill("A first draft written through the browser.");
  await page.getByRole("button", { name: "Save version" }).click();
  await expect(page.getByText(/Saved version 1/)).toBeVisible();
});
