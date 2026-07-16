import { expect, test } from "@playwright/test";

test("ordinary user can use the Docker-backed writing workspace", async ({ page, request }) => {
  const email = process.env.E2E_EMAIL ?? "e2e@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  await request.post("/api/v1/auth/setup", { data: { email, password } });
  const health = await request.get("/api/v1/health/live");
  expect(health.ok()).toBeTruthy();
  await expect(health.json()).resolves.toEqual({ status: "ok" });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /登录你的写作空间/i })).toBeVisible();
  await expect(page.getByLabel("Email")).toHaveAttribute("type", "email");
  await expect(page.getByLabel("Password")).toHaveAttribute("type", "password");

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page.getByRole("button", { name: "项目", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "English", exact: true }).click();
  await page.getByRole("button", { name: "Projects", exact: true }).click();
  await expect(page.locator("h2", { hasText: "Projects" })).toBeVisible();

  await page.getByRole("button", { name: /new project/i }).click();
  await page.getByLabel("Project title").fill(`E2E Project ${Date.now()}`);
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByRole("heading", { name: /start from your story idea/i })).toBeVisible();
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByLabel("API key").fill("mock-api-key");
  await page.getByLabel("Endpoint URL (optional)").fill("http://provider-mock:8080/v1");
  await page.getByRole("button", { name: "Save model service" }).click();
  await expect(page.getByRole("heading", { name: "Configured" })).toBeVisible();
  await page.getByRole("button", { name: "Test connection" }).last().click();
  await expect(page.getByText("openai · Connected")).toBeVisible();
  await page.getByRole("button", { name: "Outline intake" }).click();
  await page.getByLabel("Outline title").fill("E2E Outline");
  await page.getByLabel("Outline or story notes").fill("A complete story about a cartographer who returns home and chooses hope.");
  await page.getByRole("button", { name: "Import and analyze" }).click();
  const missingAnswers = page.getByPlaceholder("Answer the missing requirement");
  await expect(missingAnswers).toHaveCount(5);
  await missingAnswers.nth(0).fill("Adventure");
  await missingAnswers.nth(1).fill("Mira, a determined cartographer");
  await missingAnswers.nth(2).fill("Third person limited");
  await missingAnswers.nth(3).fill("3");
  await missingAnswers.nth(4).fill("1200");
  await page.getByRole("button", { name: "Save answer" }).click();
  await page.getByRole("button", { name: /confirm and create workflow/i }).click();
  await expect(page.getByRole("heading", { name: "Chapter workflow" })).toBeVisible();
  await page.getByRole("button", { name: "Writing Studio" }).click();
  await expect(page.getByRole("button", { name: /Chapter 1/i })).toBeVisible();
  await expect(page.locator("textarea.editor")).toHaveValue("Mock provider response", { timeout: 15_000 });
  await page.getByRole("textbox", { name: "" }).first().fill("A first draft written through the browser.");
  await page.getByRole("button", { name: "Save version" }).click();
  await expect(page.getByText(/Saved version \d+/)).toBeVisible();

  await page.getByPlaceholder(/Ask your companion/i).fill("Give me one continuity check.");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Mock provider response")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "Fork branch" }).click();
  await expect(page.getByText("Alternative branch created.")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: /Chapter 1/i })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: /sign in to your writing space/i })).toBeVisible();
});
