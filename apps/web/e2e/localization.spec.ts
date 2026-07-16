import { expect, test } from "@playwright/test";

test("localization shell is served", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#root")).toBeVisible();
});

test("authenticated user can switch navigation language", async ({ page, request }) => {
  const email = process.env.E2E_EMAIL ?? "e2e@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  await request.post("/api/v1/auth/setup", { data: { email, password } });

  await page.goto("/");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.locator(".auth-card button.primary").click();
  await expect(page.getByRole("button", { name: "English", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "English", exact: true }).click();
  await expect(page.locator("nav .nav").first()).toHaveText("Projects");
  await expect(page.getByRole("button", { name: "Usage", exact: true })).toBeVisible();

  await page.locator(".language-switcher button").first().click();
  await expect(page.locator("nav .nav").first()).not.toHaveText("Projects");
  await expect(page.locator("nav .nav").nth(6)).not.toHaveText("Usage");
});
