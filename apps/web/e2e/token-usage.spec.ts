import { expect, test } from "@playwright/test";

test("token usage API is protected until a session is established", async ({ request }) => {
  const response = await request.get("/api/v1/usage/summary");
  expect(response.status()).toBe(401);
});

test("authenticated user can inspect actual and estimated usage", async ({ page, request }) => {
  const email = process.env.E2E_EMAIL ?? "e2e@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  await request.post("/api/v1/auth/setup", { data: { email, password } });

  await page.goto("/");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码").fill(password);
  const summaryResponse = page.waitForResponse(response => response.url().includes("/api/v1/usage/summary") && response.request().method() === "GET" && response.status() === 200);
  await page.locator(".auth-card button.primary").click();
  await expect(page.getByRole("button", { name: "English", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "English", exact: true }).click();

  await page.getByRole("button", { name: "Usage", exact: true }).click();
  expect((await summaryResponse).status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Token usage" })).toBeVisible();
  await expect(page.getByText("Actual input", { exact: true })).toBeVisible();
  await expect(page.getByText("Actual output", { exact: true })).toBeVisible();
  await expect(page.getByText("Estimated total", { exact: true })).toBeVisible();
});
